import json
import logging
import os

from json_repair import loads

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import State
from prompts import *
from tools import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
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
        raise KeyError("Missing 'api_provider' in default_config.json")
    if 'model' not in run_conf:
        raise KeyError("Missing 'model' in default_config.json")
    
    provider = run_conf['api_provider']
    if provider not in api_conf:
        raise KeyError(f"Missing {provider} config in api_config.json")
    if 'url' not in api_conf[provider] or 'key' not in api_conf[provider]:
        raise KeyError(f"Missing url/key in {provider} of api_config.json")
    
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
    if not isinstance(text, str):
        return text
    if '```json' in text:
        return text.split('```json', 1)[1].split('```', 1)[0].strip()
    if '```' in text:
        parts = text.split('```')
        if len(parts) >= 3:
            return parts[1].strip()
    return text.strip()

def extract_answer(text: str):
    if not isinstance(text, str):
        return ""
    if '</think>' in text:
        answer = text.split('</think>')[-1]
        return answer.strip()
    return text

def parse_model_json(content: str):
    payload = loads(extract_json(extract_answer(content)))
    if isinstance(payload, str):
        payload = loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("Model output is not a JSON object.")
    return payload

def create_planner_node(state: State):
    logger.info('***Running Planner Node***')
    messages = [SystemMessage(content=PLAN_SYSTEM_PROMPT), HumanMessage(content=PLAN_CREATE_PROMPT.format(user_message=state['user_message']))]
    response = llm.invoke(messages)
    plan = parse_model_json(response.content)
    state['messages'] += [AIMessage(content=json.dumps(plan, ensure_ascii=False))]
    return Command(goto="execute", update={"plan": plan})

def update_planner_node(state: State):
    logger.info('***Running Update Planner Node***')
    plan = state['plan']
    goal = plan['goal']
    messages = state['messages'] + [
        SystemMessage(content=PLAN_SYSTEM_PROMPT),
        HumanMessage(content=UPDATE_PLAN_PROMPT.format(plan=plan, goal=goal))
    ]
    while True:
        response_content = ""
        try:
            response = llm.invoke(messages)
            response_content = response.content
            plan = parse_model_json(response_content)
            state['messages'] += [AIMessage(content=json.dumps(plan, ensure_ascii=False))]
            return Command(goto="execute", update={"plan": plan})
        except Exception as e:
            logger.error(f"Planner update parsing failed: {e}; content={response_content}")
            messages += [HumanMessage(content=f"Json Format Error: {e}")]

def execute_node(state: State):
    logger.info('***Running Execute Node***')
    plan = state.get('plan') or {}
    steps = plan.get('steps', [])
    current_step = None

    # Get the first incomplete step
    for step in steps:
        status = step.get('status', 'pending')
        if status != 'completed':
            current_step = step
            break
    
    logger.info(f'Current STEP: {current_step}')

    if current_step is None:
        return Command(goto='report')
    
    messages = state['observations'] + [SystemMessage(content=EXECUTE_SYSTEM_PROMPT), HumanMessage(content=EXECUTION_PROMPT.format(user_message=state['user_message'], step=current_step['description']))]

    tool_outputs = []
    
    ai_message = llm.bind_tools([create_file, str_replace, shell_exec], strict=True).invoke(messages)
    
    messages.append(ai_message)
    
    if hasattr(ai_message, 'tool_calls') and ai_message.tool_calls:
        for tool_call in ai_message.tool_calls:
            try:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                tool_result = tools[tool_name].invoke(tool_args)
                logger.info(f'tool_name: {tool_name}, tool_args: {tool_args}\ntool_result: {tool_result}')
                tool_outputs.append(f"{tool_name}: {tool_result}")
                
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
    elif isinstance(ai_message.content, str) and '<tool_call>' in ai_message.content:
        tool_call_str = ai_message.content.split('<tool_call>')[-1].split('</tool_call>')[0].strip()
        try:
            tool_call = json.loads(tool_call_str)
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            tool_result = tools[tool_name].invoke(tool_args)
            logger.info(f'Custom tool call - name: {tool_name}, args: {tool_args}, result: {tool_result}')
            tool_outputs.append(f"{tool_name}: {tool_result}")
            messages.append(AIMessage(content=f"Tool {tool_name} executed: {tool_result}"))
        except Exception as e:
            logger.error(f"Custom tool call failed: {e}")
            messages.append(AIMessage(content=f"Custom tool call error: {str(e)}"))
    answer = extract_answer(ai_message.content)
    if not answer and tool_outputs:
        answer = "\n".join(tool_outputs)

    logger.info(f'***Review of Current Step:***\n{answer}')
    state['messages'] += [AIMessage(content=answer)]
    state['observations'] += [AIMessage(content=answer)]
    return Command(goto='update_planner', update={'plan': plan})

def report_node(state: State):
    """Generates Final Report of the Task"""
    logger.info('***Running Report Node***')
    observations = state.get('observations', [])
    messages = observations + [SystemMessage(content=REPORT_SYSTEM_PROMPT)]
    final_report = ""
    
    while True:
        response = llm.bind_tools([create_file, shell_exec], strict=True).invoke(messages)
        messages.append(response)
        if getattr(response, 'tool_calls', None):
            for tool_call in response.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                if tool_name not in report_tools:
                    tool_result = {"error": f"Unknown tool: {tool_name}"}
                else:
                    tool_result = report_tools[tool_name].invoke(tool_args)
                logger.info(f'tool_name: {tool_name}, tool_args: {tool_args}\ntool_result: {tool_result}')
                messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call.get('id', ''),
                    name=tool_name
                ))
        elif isinstance(response.content, str) and '<tool_call>' in response.content:
            tool_call = response.content.split('<tool_call>')[-1].split('</tool_call>')[0].strip()
            tool_call = json.loads(tool_call)
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            if tool_name not in report_tools:
                tool_result = {"error": f"Unknown tool: {tool_name}"}
            else:
                tool_result = report_tools[tool_name].invoke(tool_args)
            logger.info(f'tool_name: {tool_name}, tool_args: {tool_args}\ntool_result: {tool_result}')
            messages.append(ToolMessage(content=str(tool_result), tool_call_id='', name=tool_name))
        else:
            final_report = extract_answer(response.content)
            break

    return {'final_report': final_report}

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
