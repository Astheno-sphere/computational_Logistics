using System;
using System.Collections.Generic;
using GH_MCP.Commands;
using GrasshopperMCP.Models;
using GrasshopperMCP.Commands;
using Grasshopper.Kernel;
using Rhino;
using System.Linq;

namespace GH_MCP.Commands
{
    /// <summary>
    /// Grasshopper 命令註冊表，用於註冊和執行命令
    /// </summary>
    public static class GrasshopperCommandRegistry
    {
        // 命令處理器字典，鍵為命令類型，值為處理命令的函數
        private static readonly Dictionary<string, Func<Command, object>> CommandHandlers = new Dictionary<string, Func<Command, object>>();

        /// <summary>
        /// 初始化命令註冊表
        /// </summary>
        public static void Initialize()
        {
            // 註冊幾何命令
            RegisterGeometryCommands();
            
            // 註冊組件命令
            RegisterComponentCommands();
            
            // 註冊文檔命令
            RegisterDocumentCommands();
            
            // 註冊意圖命令
            RegisterIntentCommands();
            
            RhinoApp.WriteLine("GH_MCP: Command registry initialized.");
        }

        /// <summary>
        /// 註冊幾何命令
        /// </summary>
        private static void RegisterGeometryCommands()
        {
            // 創建點
            RegisterCommand("create_point", GeometryCommandHandler.CreatePoint);
            
            // 創建曲線
            RegisterCommand("create_curve", GeometryCommandHandler.CreateCurve);
            
            // 創建圓
            RegisterCommand("create_circle", GeometryCommandHandler.CreateCircle);
        }

        /// <summary>
        /// 註冊組件命令
        /// </summary>
        private static void RegisterComponentCommands()
        {
            // 添加組件
            RegisterCommand("add_component", ComponentCommandHandler.AddComponent);
            
            // 連接組件
            RegisterCommand("connect_components", ConnectionCommandHandler.ConnectComponents);
            
            // 設置組件值
            RegisterCommand("set_component_value", ComponentCommandHandler.SetComponentValue);
            
            // 獲取組件信息
            RegisterCommand("get_component_info", ComponentCommandHandler.GetComponentInfo);
        }

        /// <summary>
        /// 註冊文檔命令
        /// </summary>
        private static void RegisterDocumentCommands()
        {
            // 獲取文檔信息
            RegisterCommand("get_document_info", DocumentCommandHandler.GetDocumentInfo);
            
            // 清空文檔
            RegisterCommand("clear_document", DocumentCommandHandler.ClearDocument);
            
            // 保存文檔
            RegisterCommand("save_document", DocumentCommandHandler.SaveDocument);
            
            // 加載文檔
            RegisterCommand("load_document", DocumentCommandHandler.LoadDocument);
        }

        /// <summary>
        /// 註冊意圖命令
        /// </summary>
        private static void RegisterIntentCommands()
        {
            // 創建模式
            RegisterCommand("create_pattern", IntentCommandHandler.CreatePattern);
            
            // 獲取可用模式
            RegisterCommand("get_available_patterns", IntentCommandHandler.GetAvailablePatterns);
            
            RhinoApp.WriteLine("GH_MCP: Intent commands registered.");
        }

        /// <summary>
        /// 註冊命令處理器
        /// </summary>
        /// <param name="commandType">命令類型</param>
        /// <param name="handler">處理函數</param>
        public static void RegisterCommand(string commandType, Func<Command, object> handler)
        {
            if (string.IsNullOrEmpty(commandType))
                throw new ArgumentNullException(nameof(commandType));
                
            if (handler == null)
                throw new ArgumentNullException(nameof(handler));
                
            CommandHandlers[commandType] = handler;
            RhinoApp.WriteLine($"GH_MCP: Registered command handler for '{commandType}'");
        }

        /// <summary>
        /// 執行命令
        /// </summary>
        /// <param name="command">要執行的命令</param>
        /// <returns>命令執行結果</returns>
        public static Response ExecuteCommand(Command command)
        {
            if (command == null)
            {
                return Response.CreateError("Command is null");
            }
            
            if (string.IsNullOrEmpty(command.Type))
            {
                return Response.CreateError("Command type is null or empty");
            }
            
            if (CommandHandlers.TryGetValue(command.Type, out var handler))
            {
                try
                {
                    var result = handler(command);
                    return Response.Ok(result);
                }
                catch (Exception ex)
                {
                    RhinoApp.WriteLine($"GH_MCP: Error executing command '{command.Type}': {ex.Message}");
                    return Response.CreateError($"Error executing command '{command.Type}': {ex.Message}");
                }
            }
            
            return Response.CreateError($"No handler registered for command type '{command.Type}'");
        }

        /// <summary>
        /// 獲取所有已註冊的命令類型
        /// </summary>
        /// <returns>命令類型列表</returns>
        public static List<string> GetRegisteredCommandTypes()
        {
            return CommandHandlers.Keys.ToList();
        }
    }
}
