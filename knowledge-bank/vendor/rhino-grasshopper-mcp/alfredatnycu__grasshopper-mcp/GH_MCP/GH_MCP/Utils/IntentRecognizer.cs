using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Rhino;
using GH_MCP.Models;

namespace GH_MCP.Utils
{
    /// <summary>
    /// 負責識別用戶意圖並將其轉換為具體的元件和連接
    /// </summary>
    public class IntentRecognizer
    {
        private static JObject _knowledgeBase;
        private static readonly string _knowledgeBasePath = Path.Combine(
            Path.GetDirectoryName(typeof(IntentRecognizer).Assembly.Location),
            "Resources",
            "ComponentKnowledgeBase.json"
        );

        /// <summary>
        /// 初始化知識庫
        /// </summary>
        public static void Initialize()
        {
            try
            {
                if (File.Exists(_knowledgeBasePath))
                {
                    string json = File.ReadAllText(_knowledgeBasePath);
                    _knowledgeBase = JObject.Parse(json);
                    RhinoApp.WriteLine($"Component knowledge base loaded from {_knowledgeBasePath}");
                }
                else
                {
                    RhinoApp.WriteLine($"Component knowledge base not found at {_knowledgeBasePath}");
                    _knowledgeBase = new JObject();
                }
            }
            catch (Exception ex)
            {
                RhinoApp.WriteLine($"Error loading component knowledge base: {ex.Message}");
                _knowledgeBase = new JObject();
            }
        }

        /// <summary>
        /// 從用戶描述中識別意圖
        /// </summary>
        /// <param name="description">用戶描述</param>
        /// <returns>識別到的模式名稱，如果沒有匹配則返回 null</returns>
        public static string RecognizeIntent(string description)
        {
            if (_knowledgeBase == null)
            {
                Initialize();
            }

            if (_knowledgeBase["intents"] == null)
            {
                return null;
            }

            // 將描述轉換為小寫並分割為單詞
            string[] words = description.ToLowerInvariant().Split(
                new[] { ' ', ',', '.', ';', ':', '!', '?', '(', ')', '[', ']', '{', '}' },
                StringSplitOptions.RemoveEmptyEntries
            );

            // 計算每個意圖的匹配分數
            var intentScores = new Dictionary<string, int>();

            foreach (var intent in _knowledgeBase["intents"])
            {
                string patternName = intent["pattern"].ToString();
                var keywords = intent["keywords"].ToObject<List<string>>();

                // 計算匹配的關鍵詞數量
                int matchCount = words.Count(word => keywords.Contains(word));

                if (matchCount > 0)
                {
                    intentScores[patternName] = matchCount;
                }
            }

            // 返回得分最高的意圖
            if (intentScores.Count > 0)
            {
                return intentScores.OrderByDescending(pair => pair.Value).First().Key;
            }

            return null;
        }

        /// <summary>
        /// 獲取指定模式的元件和連接
        /// </summary>
        /// <param name="patternName">模式名稱</param>
        /// <returns>包含元件和連接的元組</returns>
        public static (List<ComponentInfo> Components, List<ConnectionInfo> Connections) GetPatternDetails(string patternName)
        {
            if (_knowledgeBase == null)
            {
                Initialize();
            }

            var components = new List<ComponentInfo>();
            var connections = new List<ConnectionInfo>();

            if (_knowledgeBase["patterns"] == null)
            {
                return (components, connections);
            }

            // 查找匹配的模式
            var pattern = _knowledgeBase["patterns"].FirstOrDefault(p => p["name"].ToString() == patternName);
            if (pattern == null)
            {
                return (components, connections);
            }

            // 獲取元件信息
            foreach (var comp in pattern["components"])
            {
                var componentInfo = new ComponentInfo
                {
                    Type = comp["type"].ToString(),
                    X = comp["x"].Value<double>(),
                    Y = comp["y"].Value<double>(),
                    Id = comp["id"].ToString()
                };

                // 如果有設置，則添加設置
                if (comp["settings"] != null)
                {
                    componentInfo.Settings = comp["settings"].ToObject<Dictionary<string, object>>();
                }

                components.Add(componentInfo);
            }

            // 獲取連接信息
            foreach (var conn in pattern["connections"])
            {
                connections.Add(new ConnectionInfo
                {
                    SourceId = conn["source"].ToString(),
                    SourceParam = conn["sourceParam"].ToString(),
                    TargetId = conn["target"].ToString(),
                    TargetParam = conn["targetParam"].ToString()
                });
            }

            return (components, connections);
        }

        /// <summary>
        /// 獲取所有可用的元件類型
        /// </summary>
        /// <returns>元件類型列表</returns>
        public static List<string> GetAvailableComponentTypes()
        {
            if (_knowledgeBase == null)
            {
                Initialize();
            }

            var types = new List<string>();

            if (_knowledgeBase["components"] != null)
            {
                foreach (var comp in _knowledgeBase["components"])
                {
                    types.Add(comp["name"].ToString());
                }
            }

            return types;
        }

        /// <summary>
        /// 獲取元件的詳細信息
        /// </summary>
        /// <param name="componentType">元件類型</param>
        /// <returns>元件詳細信息</returns>
        public static JObject GetComponentDetails(string componentType)
        {
            if (_knowledgeBase == null)
            {
                Initialize();
            }

            if (_knowledgeBase["components"] != null)
            {
                var component = _knowledgeBase["components"].FirstOrDefault(
                    c => c["name"].ToString().Equals(componentType, StringComparison.OrdinalIgnoreCase)
                );

                if (component != null)
                {
                    return JObject.FromObject(component);
                }
            }

            return null;
        }
    }

    /// <summary>
    /// 元件信息類
    /// </summary>
    public class ComponentInfo
    {
        public string Type { get; set; }
        public double X { get; set; }
        public double Y { get; set; }
        public string Id { get; set; }
        public Dictionary<string, object> Settings { get; set; }
    }

    /// <summary>
    /// 連接信息類
    /// </summary>
    public class ConnectionInfo
    {
        public string SourceId { get; set; }
        public string SourceParam { get; set; }
        public string TargetId { get; set; }
        public string TargetParam { get; set; }
    }
}
