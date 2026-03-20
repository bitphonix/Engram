from setuptools import setup, find_packages

setup(
    name="engram",
    version="0.1.0",
    description="Developer decision intelligence — causal memory across AI sessions",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Your Name",
    url="https://github.com/YOUR_USERNAME/engram",
    py_modules=["engram_cli"],
    python_requires=">=3.11",
    install_requires=[
        "fastapi==0.115.0",
        "uvicorn[standard]==0.30.6",
        "langgraph==0.2.28",
        "langchain==0.3.0",
        "langchain-google-genai==2.0.0",
        "neo4j==5.20.0",
        "pymongo[srv]==4.8.0",
        "pydantic==2.9.0",
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "engram=engram_cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3.11",
    ],
)