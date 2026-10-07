using System;
using System.Collections.Generic;
using System.IO;
using GrasshopperMCP.Models;
using Grasshopper.Kernel;
using Rhino;
using System.Linq;
using System.Threading;

namespace GrasshopperMCP.Commands
{
    /// <summary>
    /// 處理文檔相關命令的處理器
    /// </summary>
    public static class DocumentCommandHandler
    {
        /// <summary>
        /// 獲取文檔信息
        /// </summary>
        /// <param name="command">命令</param>
        /// <returns>文檔信息</returns>
        public static object GetDocumentInfo(Command command)
        {
            object result = null;
            Exception exception = null;
            
            // 在 UI 線程上執行
            RhinoApp.InvokeOnUiThread(new Action(() =>
            {
                try
                {
                    // 獲取 Grasshopper 文檔
                    var doc = Grasshopper.Instances.ActiveCanvas?.Document;
                    if (doc == null)
                    {
                        throw new InvalidOperationException("No active Grasshopper document");
                    }
                    
                    // 收集組件信息
                    var components = new List<object>();
                    foreach (var obj in doc.Objects)
                    {
                        var componentInfo = new Dictionary<string, object>
                        {
                            { "id", obj.InstanceGuid.ToString() },
                            { "type", obj.GetType().Name },
                            { "name", obj.NickName }
                        };
                        
                        components.Add(componentInfo);
                    }
                    
                    // 收集文檔信息
                    var docInfo = new Dictionary<string, object>
                    {
                        { "name", doc.DisplayName },
                        { "path", doc.FilePath },
                        { "componentCount", doc.Objects.Count },
                        { "components", components }
                    };
                    
                    result = docInfo;
                }
                catch (Exception ex)
                {
                    exception = ex;
                    RhinoApp.WriteLine($"Error in GetDocumentInfo: {ex.Message}");
                }
            }));
            
            // 等待 UI 線程操作完成
            while (result == null && exception == null)
            {
                Thread.Sleep(10);
            }
            
            // 如果有異常，拋出
            if (exception != null)
            {
                throw exception;
            }
            
            return result;
        }
        
        /// <summary>
        /// 清空文檔
        /// </summary>
        /// <param name="command">命令</param>
        /// <returns>操作結果</returns>
        public static object ClearDocument(Command command)
        {
            object result = null;
            Exception exception = null;
            
            // 在 UI 線程上執行
            RhinoApp.InvokeOnUiThread(new Action(() =>
            {
                try
                {
                    // 獲取 Grasshopper 文檔
                    var doc = Grasshopper.Instances.ActiveCanvas?.Document;
                    if (doc == null)
                    {
                        throw new InvalidOperationException("No active Grasshopper document");
                    }
                    
                    // 創建一個新的文檔對象列表，避免在遍歷時修改集合
                    var objectsToRemove = doc.Objects.ToList();
                    
                    // 過濾掉必要的元件（保留那些用於與 Claude Desktop 通信的元件）
                    // 這裡我們可以通過 GUID、名稱或類型來識別必要的元件
                    var essentialComponents = objectsToRemove.Where(obj => 
                        // 檢查元件的名稱是否包含特定關鍵字
                        obj.NickName.Contains("MCP") || 
                        obj.NickName.Contains("Claude") ||
                        // 或者檢查元件的類型
                        obj.GetType().Name.Contains("GH_MCP") ||
                        // 或者檢查元件的描述
                        obj.Description.Contains("Machine Control Protocol") ||
                        // 保留 toggle 元件
                        obj.GetType().Name.Contains("GH_BooleanToggle") ||
                        // 保留 panel 元件 (用於顯示 status)
                        obj.GetType().Name.Contains("GH_Panel") ||
                        // 額外檢查元件名稱
                        obj.NickName.Contains("Toggle") ||
                        obj.NickName.Contains("Status") ||
                        obj.NickName.Contains("Panel")
                    ).ToList();
                    
                    // 從要刪除的列表中移除必要的元件
                    foreach (var component in essentialComponents)
                    {
                        objectsToRemove.Remove(component);
                    }
                    
                    // 清空文檔（只刪除非必要的元件）
                    doc.RemoveObjects(objectsToRemove, false);
                    
                    // 刷新畫布
                    doc.NewSolution(false);
                    
                    // 返回操作結果
                    result = new
                    {
                        success = true,
                        message = "Document cleared"
                    };
                }
                catch (Exception ex)
                {
                    exception = ex;
                    RhinoApp.WriteLine($"Error in ClearDocument: {ex.Message}");
                }
            }));
            
            // 等待 UI 線程操作完成
            while (result == null && exception == null)
            {
                Thread.Sleep(10);
            }
            
            // 如果有異常，拋出
            if (exception != null)
            {
                throw exception;
            }
            
            return result;
        }
        
        /// <summary>
        /// 保存文檔
        /// </summary>
        /// <param name="command">命令</param>
        /// <returns>操作結果</returns>
        public static object SaveDocument(Command command)
        {
            string path = command.GetParameter<string>("path");
            if (string.IsNullOrEmpty(path))
            {
                throw new ArgumentException("Save path is required");
            }
            
            // 返回一個錯誤信息，表示該功能暫時不可用
            return new
            {
                success = false,
                message = "SaveDocument is temporarily disabled due to API compatibility issues. Please save the document manually."
            };
        }
        
        /// <summary>
        /// 加載文檔
        /// </summary>
        /// <param name="command">命令</param>
        /// <returns>操作結果</returns>
        public static object LoadDocument(Command command)
        {
            string path = command.GetParameter<string>("path");
            if (string.IsNullOrEmpty(path))
            {
                throw new ArgumentException("Load path is required");
            }
            
            // 返回一個錯誤信息，表示該功能暫時不可用
            return new
            {
                success = false,
                message = "LoadDocument is temporarily disabled due to API compatibility issues. Please load the document manually."
            };
        }
    }
}
