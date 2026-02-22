from langchain_core.tools import tool
import os
import subprocess
from pathlib import Path


@tool
def create_file(file_name, file_contents):
    """
    Create a new file with the provided contents at a given path in the workspace.

    args:
        file_name (str): Name to the file to be created
        file_contents (str): The content to write to the file
    """
    try:
        file_path = Path(os.getcwd()) / file_name
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(file_contents)
        return {
            "success": True,
            "file_path": str(file_path)
        }

    except Exception as e:
        return {
            "error": str(e)
        }

@tool
def str_replace(file_name, search, replace):
    """
    Replace specific text in a file.
    
    args:
        file_name (str): Name to the target file
        old_str (str): Text to be replaced (must appear exactly once)
        new_str (str): Replacement text
    """
    try:
        file_path = Path(file_name)
        text = file_path.read_text(encoding='utf-8')
        occurrences = text.count(search)
        if occurrences == 0:
            return {"success": False, "error": "search text not found"}
        if occurrences > 1:
            return {"success": False, "error": "search text is ambiguous"}

        text = text.replace(search, replace, 1)
        file_path.write_text(text, encoding='utf-8')
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def send_message(message: str):
    """
    send a message to the user
    
    args:
        message: the message to send to the user
    """
    return message


@tool
def shell_exec(command: str) -> dict:
    """
    Execute command in specified shell session.

    args:
        command (str): the shell command to execute
    
    returns:
        dict:
            - stdout: standard output of the command
            - stderr: standard error of the command
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            check=False
        )
        res = {
            "message": {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        }
        return res
        
    except Exception as e:
        return {"error": {"stderr": str(e), "returncode": -1}}
    
tools = {"create_file": create_file, "str_replace": str_replace, "shell_exec": shell_exec}     
report_tools = {"create_file": create_file, "shell_exec": shell_exec}     
