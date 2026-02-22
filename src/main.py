import argparse

from workflow import build_graph, build_graph_with_memory


def main():
    parser = argparse.ArgumentParser(description="Command Line Tool for Simple-Coder")
    parser.add_argument('--memory', '-m', action='store_true', help='Whether to activate memory')

    args = parser.parse_args()
    if args.memory:
        graph = build_graph_with_memory()
    else:
        graph = build_graph()

    user_message = input('Please enter your request here:\n') # Help me train a CNN classifier on MNIST with pytorch
    inputs = {
        "user_message": user_message,
        "plan": None,
        "observations": [],
        "final_report": ""
    }
    invoke_config = {"recursion_limit": 100}
    if args.memory:
        invoke_config["configurable"] = {"thread_id": "default"}

    graph.invoke(inputs, invoke_config)


if __name__ == "__main__":
    main()
