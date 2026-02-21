from langchain_core.tools import tool
import os
import traceback
import subprocess
import tempfile
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
        file_path = os.path.join(os.getcwd(), file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w') as file:
            file.write(file_contents)

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
    text = Path(file_name).read_text()
    if search not in text:
        return {"success": False}
    text = text.replace(search, replace)
    Path(file_name).write_text(text)
    return {"success": True}

@tool
def send_message(message: str):
    """
    send a message to the user
    
    args:
        message: the message to send to the user
    """
    return message
tool()
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
        stdout = result.stdout if len(result.stdout) else 'Success'
        res = {"message": {"stdout": stdout}}
        if len(result.stderr): res.update({"stderr": result.stderr}) 
        return res
        
    except Exception as e:
        return {"error": {"stderr": str(e)}}
    
tools = {"create_file": create_file, "str_replace": str_replace, "shell_exec": shell_exec}     
report_tools = {"create_file": create_file, "shell_exec": shell_exec}     
