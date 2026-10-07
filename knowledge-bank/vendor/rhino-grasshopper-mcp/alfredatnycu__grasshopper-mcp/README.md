# Grasshopper MCP Bridge

Grasshopper MCP Bridge is a bridging server that connects Grasshopper and Claude Desktop using the Model Context Protocol (MCP) standard.

## Features

- Connects Grasshopper and Claude Desktop through the MCP protocol
- Provides intuitive tool functions for creating and connecting Grasshopper components
- Supports high-level intent recognition, automatically creating complex component patterns from simple descriptions
- Includes a component knowledge base that understands parameters and connection rules for common components
- Provides component guidance resources to help Claude Desktop correctly connect components

## System Architecture

The system consists of the following parts:

1. **Grasshopper MCP Component (GH_MCP.gha)**: A plugin installed in Grasshopper that provides a TCP server to receive commands
2. **Python MCP Bridge Server**: A bridge server that connects Claude Desktop and the Grasshopper MCP component
3. **Component Knowledge Base**: JSON files containing component information, patterns, and intents

## Installation Instructions

### Prerequisites

- Rhino 7 or higher
- Grasshopper
- Python 3.8 or higher
- Claude Desktop

### Installation Steps

1. **Install the Grasshopper MCP Component**

   **Method 1: Download the pre-compiled GH_MCP.gha file (Recommended)**
   
   Download the [GH_MCP.gha](https://github.com/alfredatnycu/grasshopper-mcp/raw/master/releases/GH_MCP.gha) file directly from the GitHub repository and copy it to the Grasshopper components folder:
   ```
   %APPDATA%\Grasshopper\Libraries\
   ```

   **Method 2: Build from source**
   
   If you prefer to build from source, clone the repository and build the C# project using Visual Studio.

2. **Install the Python MCP Bridge Server**

   **Method 1: Install from PyPI (Recommended)**
   
   The simplest method is to install directly from PyPI using pip:
   ```
   pip install grasshopper-mcp
   ```
   
   **Method 2: Install from GitHub**
   
   You can also install the latest version from GitHub:
   ```
   pip install git+https://github.com/alfredatnycu/grasshopper-mcp.git
   ```
   
   **Method 3: Install from Source Code**
   
   If you need to modify the code or develop new features, you can clone the repository and install:
   ```
   git clone https://github.com/alfredatnycu/grasshopper-mcp.git
   cd grasshopper-mcp
   pip install -e .
   ```

   **Install a Specific Version**
   
   If you need to install a specific version, you can use:
   ```
   pip install grasshopper-mcp==0.1.0
   ```
   Or install from a specific GitHub tag:
   ```
   pip install git+https://github.com/alfredatnycu/grasshopper-mcp.git@v0.1.0
   ```

## Usage

1. **Start Rhino and Grasshopper**

   Launch Rhino and open Grasshopper.

2. **Add the GH_MCP Component to Your Canvas**

   Find the GH_MCP component in the Grasshopper component panel and add it to your canvas.

3. **Start the Python MCP Bridge Server**

   Open a terminal and run:
   ```
   python -m grasshopper_mcp.bridge
   ```
   
   > **Note**: The command `grasshopper-mcp` might not work directly due to Python script path issues. Using `python -m grasshopper_mcp.bridge` is the recommended and more reliable method.

4. **Connect Claude Desktop to the MCP Bridge**

   **Method 1: Manual Connection**
   
   In Claude Desktop, connect to the MCP Bridge server using the following settings:
   - Protocol: MCP
   - Host: localhost
   - Port: 8080

   **Method 2: Configure Claude Desktop to Auto-Start the Bridge**
   
   You can configure Claude Desktop to automatically start the MCP Bridge server by modifying its configuration:
   
   ```json
   "grasshopper": {
     "command": "python",
     "args": ["-m", "grasshopper_mcp.bridge"]
   }
   ```
   
   This configuration tells Claude Desktop to use the command `python -m grasshopper_mcp.bridge` to start the MCP server.

5. **Start Using Grasshopper with Claude Desktop**

   You can now use Claude Desktop to control Grasshopper through natural language commands.

## Example Commands

Here are some example commands you can use with Claude Desktop:

- "Create a circle with radius 5 at point (0,0,0)"
- "Connect the circle to a extrude component with a height of 10"
- "Create a grid of points with 5 rows and 5 columns"
- "Apply a random rotation to all selected objects"

## Troubleshooting

If you encounter issues, check the following:

1. **GH_MCP Component Not Loading**
   - Ensure the .gha file is in the correct location
   - In Grasshopper, go to File > Preferences > Libraries and click "Unblock" to unblock new components
   - Restart Rhino and Grasshopper

2. **Bridge Server Won't Start**
   - If `grasshopper-mcp` command doesn't work, use `python -m grasshopper_mcp.bridge` instead
   - Ensure all required Python dependencies are installed
   - Check if port 8080 is already in use by another application

3. **Claude Desktop Can't Connect**
   - Ensure the bridge server is running
   - Verify you're using the correct connection settings (localhost:8080)
   - Check the console output of the bridge server for any error messages

4. **Commands Not Executing**
   - Verify the GH_MCP component is on your Grasshopper canvas
   - Check the bridge server console for error messages
   - Ensure Claude Desktop is properly connected to the bridge server

## Development

### Project Structure

```
grasshopper-mcp/
├── grasshopper_mcp/       # Python bridge server
│   ├── __init__.py
│   └── bridge.py          # Main bridge server implementation
├── GH_MCP/                # Grasshopper component (C#)
│   └── ...
├── releases/              # Pre-compiled binaries
│   └── GH_MCP.gha         # Compiled Grasshopper component
├── setup.py               # Python package setup
└── README.md              # This file
```

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to the Rhino and Grasshopper community for their excellent tools
- Thanks to Anthropic for Claude Desktop and the MCP protocol

## Contact

For questions or support, please open an issue on the GitHub repository.
