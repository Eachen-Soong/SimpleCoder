# User Guide
Run ```pip install -e .``` to install.

Run ```mkdir ~/.config/simp-code; vim ~/.config/simp-code/api_config.json```, and add your configuration as follows:
```
{
    "Qwen": {
        "key_name": "DASHSCOPE_API_KEY",
        "key": "YOUR_API_KEY",
        "url": "https://dashscope.aliyuncs.com/compatible-mode",
        "model_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
    },
    "DeepSeek": {
        "key_name": "DEEPSEEK_API_KEY",
        "key": "YOUR_API_KEY",
        "url": "https://api.deepseek.com",
        "model_url": "https://api.deepseek.com/v1/models",
    }
}
```
Run ```vim ~/.config/simp-code/default_config.json```, and add your default configuration as follows:
{
    "api_privider": "DeepSeek",
    "model": "deepseek-chat"
}

and run ```simp-code -m 1``` to activate memory mode, or simply ```simp-code```.# SimpleCoder
# SimpleCoder
# SimpleCoder
