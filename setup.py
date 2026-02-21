# setup.py
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="Simple Coder",
    version="0.1.0",
    author="Eachen Soong",
    author_email="stopratracingplz@gmail.com",
    description="基于LangGraph和OpenAI的命令行工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # url="https://github.com/your/repo",

    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",

    entry_points={
        "console_scripts": [
            "simp-code = main:main",
        ]
    },

    install_requires=[
        "langchain-core>=0.3.0",
        "langchain-openai>=0.1.0",
        "langgraph>=0.1.0",
        "pydantic>=2.0.0",
        "openai>=1.0.0",
        "python-dotenv>=1.0.0",
        "json_repair?=0.50"
    ],

    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)