using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using GrasshopperMCP.Models;
using GrasshopperMCP.Commands;
using GH_MCP.Models;
using GH_MCP.Utils;
using Rhino;
using Newtonsoft.Json;

namespace GH_MCP.Commands
{
    /// <summary>
    /// 處理高層次意圖命令的處理器
    /// </summary>
    public class IntentCommandHandler
    {
        private static Dictionary<string, string> _componentIdMap = new Dictionary<string, string>();

        /// <summary>
        /// 處理創建模式命令
        /// </summary>
        /// <param name="command">命令對象</param>
        /// <returns>命令執行結果</returns>
        public static object CreatePattern(Command command)
        {
            // 獲取模式名稱或描述
            if (!command.Parameters.TryGetValue("description", out object descriptionObj) || descriptionObj == null)
            {
                return Response.CreateError("Missing required parameter: description");
            }
            string description = descriptionObj.ToString();

            // 識別意圖
            string patternName = IntentRecognizer.RecognizeIntent(description);
            if (string.IsNullOrEmpty(patternName))
            {
                return Response.CreateError($"Could not recognize intent from description: {description}");
            }

            RhinoApp.WriteLine($"Recognized intent: {patternName}");

            // 獲取模式詳細信息
            var (components, connections) = IntentRecognizer.GetPatternDetails(patternName);
            if (components.Count == 0)
            {
                return Response.CreateError($"Pattern '{patternName}' has no components defined");
            }

            // 清空組件 ID 映射
            _componentIdMap.Clear();

            // 創建所有組件
            foreach (var component in components)
            {
                try
                {
                    // 創建組件命令
                    var addCommand = new Command(
                        "add_component",
                        new Dictionary<string, object>
                        {
                            { "type", component.Type },
                            { "x", component.X },
                            { "y", component.Y }
                        }
                    );

                    // 如果有設置，添加設置
                    if (component.Settings != null)
                    {
                        foreach (var setting in component.Settings)
                        {
                            addCommand.Parameters.Add(setting.Key, setting.Value);
                        }
                    }

                    // 執行添加組件命令
                    var result = ComponentCommandHandler.AddComponent(addCommand);
                    if (result is Response response && response.Success && response.Data != null)
                    {
                        // 保存組件 ID 映射
                        string componentId = response.Data.ToString();
                        _componentIdMap[component.Id] = componentId;
                        RhinoApp.WriteLine($"Created component {component.Type} with ID {componentId}");
                    }
                    else
                    {
                        RhinoApp.WriteLine($"Failed to create component {component.Type}");
                    }
                }
                catch (Exception ex)
                {
                    RhinoApp.WriteLine($"Error creating component {component.Type}: {ex.Message}");
                }

                // 添加短暫延遲，確保組件創建完成
                Thread.Sleep(100);
            }

            // 創建所有連接
            foreach (var connection in connections)
            {
                try
                {
                    // 檢查源和目標組件 ID 是否存在
                    if (!_componentIdMap.TryGetValue(connection.SourceId, out string sourceId) ||
                        !_componentIdMap.TryGetValue(connection.TargetId, out string targetId))
                    {
                        RhinoApp.WriteLine($"Could not find component IDs for connection {connection.SourceId} -> {connection.TargetId}");
                        continue;
                    }

                    // 創建連接命令
                    var connectCommand = new Command(
                        "connect_components",
                        new Dictionary<string, object>
                        {
                            { "sourceId", sourceId },
                            { "sourceParam", connection.SourceParam },
                            { "targetId", targetId },
                            { "targetParam", connection.TargetParam }
                        }
                    );

                    // 執行連接命令
                    var result = ConnectionCommandHandler.ConnectComponents(connectCommand);
                    if (result is Response response && response.Success)
                    {
                        RhinoApp.WriteLine($"Connected {connection.SourceId}.{connection.SourceParam} -> {connection.TargetId}.{connection.TargetParam}");
                    }
                    else
                    {
                        RhinoApp.WriteLine($"Failed to connect {connection.SourceId}.{connection.SourceParam} -> {connection.TargetId}.{connection.TargetParam}");
                    }
                }
                catch (Exception ex)
                {
                    RhinoApp.WriteLine($"Error creating connection: {ex.Message}");
                }

                // 添加短暫延遲，確保連接創建完成
                Thread.Sleep(100);
            }

            // 返回成功結果
            return Response.Ok(new
            {
                Pattern = patternName,
                ComponentCount = components.Count,
                ConnectionCount = connections.Count
            });
        }

        /// <summary>
        /// 獲取可用的模式列表
        /// </summary>
        /// <param name="command">命令對象</param>
        /// <returns>命令執行結果</returns>
        public static object GetAvailablePatterns(Command command)
        {
            // 初始化意圖識別器
            IntentRecognizer.Initialize();

            // 獲取所有可用的模式
            var patterns = new List<string>();
            if (command.Parameters.TryGetValue("query", out object queryObj) && queryObj != null)
            {
                string query = queryObj.ToString();
                string patternName = IntentRecognizer.RecognizeIntent(query);
                if (!string.IsNullOrEmpty(patternName))
                {
                    patterns.Add(patternName);
                }
            }
            else
            {
                // 如果沒有查詢，返回所有模式
                // 這裡需要擴展 IntentRecognizer 以支持獲取所有模式
                // 暫時返回空列表
            }

            // 返回成功結果
            return Response.Ok(patterns);
        }
    }
}
