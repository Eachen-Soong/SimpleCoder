import argparse

from workflow import build_graph, build_graph_with_memory

def main():
    parser = argparse.ArgumentParser(description="Command Line Tool for Simple-Coder")
    parser.add_argument('--memory', '-m', type=int, default=0, help='Whether to activate memory')

    args = parser.parse_args()
    if args.memory:
        graph = build_graph_with_memory()
    else:
        graph = build_graph()

    inputs = {  "user_message": input('Please enter your request here:\n'), # Help me train a CNN classifier on MNIST
                "plan": None,
                "observations": [],
                "final_report": ""}

    graph.invoke(inputs, {"recursion_limit":100})