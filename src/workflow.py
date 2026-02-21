import json
import logging
from json_repair import loads

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command, Interrupt
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import State
from prompts import *
from tools import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

llm = None
try:
    config_dir = os.path.expanduser('~/.config/simp-code')
    if not os.path.exists(config_dir):
        raise FileNotFoundError(f"Config directory not found: {config_dir}")
    
    with open(os.path.join(config_dir, 'api_config.json')) as f:
        api_conf = json.load(f)
    with open(os.path.join(config_dir, 'default_config.json')) as f:
        run_conf = json.load(f)
    
    if 'api_provider' not in run_conf:
        raise KeyError("default_config.json 中缺少 'api_provider' 字段")
    if 'model' not in run_conf:
        raise KeyError("default_config.json 中缺少 'model' 字段")
    
    provider = run_conf['api_provider']
    if provider not in api_conf:
        raise KeyError(f"api_config.json 中缺少 {provider} 配置")
    if 'url' not in api_conf[provider] or 'key' not in api_conf[provider]:
        raise KeyError(f"api_config.json 中 {provider} 缺少 url/key 字段")
    
    llm = ChatOpenAI(
        model=run_conf['model'],
        base_url=api_conf[provider]['url'],
        api_key=api_conf[provider]['key'],
        temperature=0
    )
    logger.info(f"LLM initialized successfully (model: {run_conf['model']})")
except Exception as e:
    error_msg = f'Config load failed: {str(e)}\nPlease check files in ~/.config/simp-code'
    print(error_msg)
    raise SystemExit(error_msg) from e


def extract_json(text: str):
    if '```json' not in text:
        return text
    text = text.split('```json')[1].split('```')[0].strip()
    text = json.dumps(text,ensure_ascii=False)
    return text

def extract_answer(text: str):
    if '</think>' in text:
        answer = text.split('</think>')[-1]
        return answer.strip()
    return text

def create_planner_node(state: State):
    logger.info('***Running Planner Node***')
    messages = [SystemMessage(content=PLAN_SYSTEM_PROMPT), HumanMessage(content=PLAN_CREATE_PROMPT.format(user_message=state['user_message']))]
    response = llm.invoke(messages).model_dump_json(indent=4, exclude_none=True)
    response = json.loads(response)
    plan = loads(extract_json(extract_answer(response['content'])))
    state['messages'] += [AIMessage(content=json.dumps(plan, ensure_ascii=False))]
    return Command(goto="execute", update={"plan": plan})

def update_planner_node(state: State):
    logger.info('***Running Update Planner Node***')
    plan = state['plan']
    goal = plan['goal']
    state['messages'].extend([SystemMessage(content=PLAN_SYSTEM_PROMPT), HumanMessage(content=UPDATE_PLAN_PROMPT.format(plan=plan, goal=goal))])
    messages = state['messages']
    while True:
        try:
            response = llm.invoke(messages).model_dump_json(indent=4, exclude_none=True)
            response = json.loads(response)
            plan = loads(extract_json(extract_answer(response['content'])))
            state['messages'] += [AIMessage(content=json.dumps(plan, ensure_ascii=False))]
            return Command(goto="execute", update={"plan": plan})
        except Exception as e:
            print(e)
            print(response)
            messages += [HumanMessage(content=f"Json Format Error: {e}")]

def execute_node(state: State):
    logger.info('***Running Execute Node***')
    plan = state['plan']
    steps = plan['steps']
    current_step = None
    current_step_index = 0

    # Get the first incomplete step
    for i, step in enumerate(steps):
        status = step['status']
        if status == 'pending':
            current_step = step
            current_step_index = i
            break
    
    logger.info(f'Current STEP: {current_step}')

    if current_step is None or current_step_index == len(steps)-1:
        return Command(goto='report')
    
    messages = state['observations'] + [SystemMessage(content=EXECUTE_SYSTEM_PROMPT), HumanMessage(content=EXECUTION_PROMPT.format(user_message=state['user_message'], step=current_step['description']))]

    tool_result = None
    
    response = llm.bind_tools([create_file, str_replace, shell_exec], strict=True).invoke(messages)
    ai_message = response
    
    messages.append(ai_message)
    
    if hasattr(ai_message, 'tool_calls') and ai_message.tool_calls:
        for tool_call in ai_message.tool_calls:
            try:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                tool_result = tools[tool_name].invoke(tool_args)
                logger.info(f'tool_name: {tool_name}, tool_args: {tool_args}\ntool_result: {tool_result}')
                
                tool_message = ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call['id'],
                    name=tool_name
                )
                messages.append(tool_message)
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                tool_message = ToolMessage(
                    content=f"Tool execution error: {str(e)}",
                    tool_call_id=tool_call['id'],
                    name=tool_call['name']
                )
                messages.append(tool_message)
    elif '<tool_call>' in ai_message.content:
        tool_call_str = ai_message.content.split('<tool_call>')[-1].split('</tool_call>')[0].strip()
        try:
            tool_call = json.loads(tool_call_str)
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            tool_result = tools[tool_name].invoke(tool_args)
            logger.info(f'Custom tool call - name: {tool_name}, args: {tool_args}, result: {tool_result}')
            messages.append(AIMessage(content=f"Tool {tool_name} executed: {tool_result}"))
        except Exception as e:
            logger.error(f"Custom tool call failed: {e}")
            messages.append(AIMessage(content=f"Custom tool call error: {str(e)}"))
    answer = extract_answer(ai_message.content)

    logger.info(f'***Review of Current Step:***\n{answer}')
    state['messages'] += [AIMessage(content=answer)]
    state['observations'] += [AIMessage(content=answer)]
    return Command(goto='update_planner', update={'plan': plan})

def report_node(state: State):
    """Generates Final Report of the Task"""
    logger.info('***Running Report Node***')
    observations = state.get('observations')
    messages = observations + [SystemMessage(content=REPORT_SYSTEM_PROMPT)]
    
    while True:
        response = llm.bind_tools([create_file, shell_exec], strict=True).invoke(messages)
        response = response.model_dump_json(indent=4, exclude_none=True)
        response = json.loads(response)
        if response['tool_calls']:
            for tool_call in response['tool_calls']:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                tool_result = report_tools[tool_name].invoke(tool_args)
                logger.info(f'tool_name: {tool_name}, tool_args: {tool_args}\ntool_result: {tool_result}')
                messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call.get('id', '')
                ))
        elif '<tool_call>' in response['content']:
            tool_call = response['content'].split('<tool_call>')[-1].split('</tool_call>')[0].strip()
            tool_call = json.loads(tool_call)
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            tool_result = report_tools[tool_name].invoke(tool_args)
            logger.info(f'tool_name: {tool_name}, tool_args: {tool_args}\ntool_result: {tool_result}')
            messages.append(ToolMessage(content=str(tool_result)))
        else: break

    return {'final_report': response['content']}

def _build_base_graph():
    """Build and return the base state graph with all nodes and edges."""
    builder = StateGraph(State)
    builder.add_edge(START, 'create_planner')
    builder.add_node('create_planner', create_planner_node)
    builder.add_node('update_planner', update_planner_node)
    builder.add_node('execute', execute_node)
    builder.add_node('report', report_node)
    builder.add_edge('report', END)
    return builder

def build_graph_with_memory():
    """Build and return agent workflow graph with memory."""
    memory = MemorySaver()
    builder = _build_base_graph()
    return builder.compile(checkpointer=memory)

def build_graph():
    """Build and return agent workflow graph without memory."""
    builder = _build_base_graph()
    return builder.compile()
