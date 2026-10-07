from setuptools import setup, find_packages
import os

# 讀取 README.md 作為長描述
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="grasshopper-mcp",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "mcp>=0.1.0",
        "websockets>=10.0",
        "aiohttp>=3.8.0",
    ],
    entry_points={
        "console_scripts": [
            "grasshopper-mcp=grasshopper_mcp.bridge:main",
        ],
    },
    author="Alfred Chen",
    author_email="yanlin.hs12@nycu.edu.tw",
    description="Grasshopper MCP Bridge Server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="grasshopper, mcp, bridge, server",
    url="https://github.com/alfredatnycu/grasshopper-mcp",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.8",
)
