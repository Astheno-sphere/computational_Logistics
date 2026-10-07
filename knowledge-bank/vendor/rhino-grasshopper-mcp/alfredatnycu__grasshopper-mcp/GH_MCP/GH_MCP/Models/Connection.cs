using System;

namespace GH_MCP.Models
{
    /// <summary>
    /// 表示一個組件連接端點
    /// </summary>
    public class Connection
    {
        /// <summary>
        /// 組件的 GUID
        /// </summary>
        public string ComponentId { get; set; }

        /// <summary>
        /// 參數名稱（輸入或輸出參數）
        /// </summary>
        public string ParameterName { get; set; }

        /// <summary>
        /// 參數索引（如果未指定名稱，則使用索引）
        /// </summary>
        public int? ParameterIndex { get; set; }

        /// <summary>
        /// 檢查連接是否有效
        /// </summary>
        public bool IsValid()
        {
            return !string.IsNullOrEmpty(ComponentId) && 
                   (!string.IsNullOrEmpty(ParameterName) || ParameterIndex.HasValue);
        }
    }

    /// <summary>
    /// 表示兩個組件之間的連接
    /// </summary>
    public class ConnectionPairing
    {
        /// <summary>
        /// 源組件連接（輸出端）
        /// </summary>
        public Connection Source { get; set; }

        /// <summary>
        /// 目標組件連接（輸入端）
        /// </summary>
        public Connection Target { get; set; }

        /// <summary>
        /// 檢查連接配對是否有效
        /// </summary>
        public bool IsValid()
        {
            return Source != null && Target != null && Source.IsValid() && Target.IsValid();
        }
    }
}
