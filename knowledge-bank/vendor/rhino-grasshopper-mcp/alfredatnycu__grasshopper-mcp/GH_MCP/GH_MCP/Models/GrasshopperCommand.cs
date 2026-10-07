using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace GrasshopperMCP.Models
{
    /// <summary>
    /// 表示從 Python 伺服器發送到 Grasshopper 的命令
    /// </summary>
    public class Command
    {
        /// <summary>
        /// 命令類型
        /// </summary>
        [JsonProperty("type")]
        public string Type { get; set; }

        /// <summary>
        /// 命令參數
        /// </summary>
        [JsonProperty("parameters")]
        public Dictionary<string, object> Parameters { get; set; }

        /// <summary>
        /// 創建一個新的命令實例
        /// </summary>
        /// <param name="type">命令類型</param>
        /// <param name="parameters">命令參數</param>
        public Command(string type, Dictionary<string, object> parameters = null)
        {
            Type = type;
            Parameters = parameters ?? new Dictionary<string, object>();
        }

        /// <summary>
        /// 獲取指定參數的值
        /// </summary>
        /// <typeparam name="T">參數類型</typeparam>
        /// <param name="name">參數名稱</param>
        /// <returns>參數值</returns>
        public T GetParameter<T>(string name)
        {
            if (Parameters.TryGetValue(name, out object value))
            {
                if (value is T typedValue)
                {
                    return typedValue;
                }
                
                // 嘗試轉換
                try
                {
                    return (T)Convert.ChangeType(value, typeof(T));
                }
                catch
                {
                    // 如果是 Newtonsoft.Json.Linq.JObject，嘗試轉換
                    if (value is Newtonsoft.Json.Linq.JObject jObject)
                    {
                        return jObject.ToObject<T>();
                    }
                    
                    // 如果是 Newtonsoft.Json.Linq.JArray，嘗試轉換
                    if (value is Newtonsoft.Json.Linq.JArray jArray)
                    {
                        return jArray.ToObject<T>();
                    }
                }
            }
            
            // 如果無法獲取或轉換參數，返回默認值
            return default;
        }
    }

    /// <summary>
    /// 表示從 Grasshopper 發送到 Python 伺服器的響應
    /// </summary>
    public class Response
    {
        /// <summary>
        /// 響應是否成功
        /// </summary>
        [JsonProperty("success")]
        public bool Success { get; set; }

        /// <summary>
        /// 響應數據
        /// </summary>
        [JsonProperty("data")]
        public object Data { get; set; }

        /// <summary>
        /// 錯誤信息，如果有的話
        /// </summary>
        [JsonProperty("error")]
        public string Error { get; set; }

        /// <summary>
        /// 創建一個成功的響應
        /// </summary>
        /// <param name="data">響應數據</param>
        /// <returns>響應實例</returns>
        public static Response Ok(object data = null)
        {
            return new Response
            {
                Success = true,
                Data = data
            };
        }

        /// <summary>
        /// 創建一個錯誤的響應
        /// </summary>
        /// <param name="errorMessage">錯誤信息</param>
        /// <returns>響應實例</returns>
        public static Response CreateError(string errorMessage)
        {
            return new Response
            {
                Success = false,
                Data = null,
                Error = errorMessage
            };
        }
    }
}
