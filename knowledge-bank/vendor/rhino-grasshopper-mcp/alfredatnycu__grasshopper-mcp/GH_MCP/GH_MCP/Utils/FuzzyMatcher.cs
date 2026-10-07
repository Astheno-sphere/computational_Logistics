using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace GH_MCP.Utils
{
    /// <summary>
    /// 提供模糊匹配功能的工具類
    /// </summary>
    public static class FuzzyMatcher
    {
        // 元件名稱映射字典，將常用的簡化名稱映射到實際的 Grasshopper 元件名稱
        private static readonly Dictionary<string, string> ComponentNameMap = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            // 平面元件
            { "plane", "XY Plane" },
            { "xyplane", "XY Plane" },
            { "xy", "XY Plane" },
            { "xzplane", "XZ Plane" },
            { "xz", "XZ Plane" },
            { "yzplane", "YZ Plane" },
            { "yz", "YZ Plane" },
            { "plane3pt", "Plane 3Pt" },
            { "3ptplane", "Plane 3Pt" },
            
            // 基本幾何元件
            { "box", "Box" },
            { "cube", "Box" },
            { "rectangle", "Rectangle" },
            { "rect", "Rectangle" },
            { "circle", "Circle" },
            { "circ", "Circle" },
            { "sphere", "Sphere" },
            { "cylinder", "Cylinder" },
            { "cyl", "Cylinder" },
            { "cone", "Cone" },
            
            // 參數元件
            { "slider", "Number Slider" },
            { "numberslider", "Number Slider" },
            { "panel", "Panel" },
            { "point", "Point" },
            { "pt", "Point" },
            { "line", "Line" },
            { "ln", "Line" },
            { "curve", "Curve" },
            { "crv", "Curve" }
        };
        
        // 參數名稱映射字典，將常用的簡化參數名稱映射到實際的 Grasshopper 參數名稱
        private static readonly Dictionary<string, string> ParameterNameMap = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            // 平面參數
            { "plane", "Plane" },
            { "base", "Base" },
            { "origin", "Origin" },
            
            // 尺寸參數
            { "radius", "Radius" },
            { "r", "Radius" },
            { "size", "Size" },
            { "xsize", "X Size" },
            { "ysize", "Y Size" },
            { "zsize", "Z Size" },
            { "width", "X Size" },
            { "length", "Y Size" },
            { "height", "Z Size" },
            { "x", "X" },
            { "y", "Y" },
            { "z", "Z" },
            
            // 點參數
            { "point", "Point" },
            { "pt", "Point" },
            { "center", "Center" },
            { "start", "Start" },
            { "end", "End" },
            
            // 數值參數
            { "number", "Number" },
            { "num", "Number" },
            { "value", "Value" },
            
            // 輸出參數
            { "result", "Result" },
            { "output", "Output" },
            { "geometry", "Geometry" },
            { "geo", "Geometry" },
            { "brep", "Brep" }
        };
        
        /// <summary>
        /// 獲取最接近的元件名稱
        /// </summary>
        /// <param name="input">輸入的元件名稱</param>
        /// <returns>映射後的元件名稱</returns>
        public static string GetClosestComponentName(string input)
        {
            if (string.IsNullOrWhiteSpace(input))
                return input;
                
            // 嘗試直接映射
            string normalizedInput = input.ToLowerInvariant().Replace(" ", "").Replace("_", "");
            if (ComponentNameMap.TryGetValue(normalizedInput, out string mappedName))
                return mappedName;
                
            // 如果沒有直接映射，返回原始輸入
            return input;
        }
        
        /// <summary>
        /// 獲取最接近的參數名稱
        /// </summary>
        /// <param name="input">輸入的參數名稱</param>
        /// <returns>映射後的參數名稱</returns>
        public static string GetClosestParameterName(string input)
        {
            if (string.IsNullOrWhiteSpace(input))
                return input;
                
            // 嘗試直接映射
            string normalizedInput = input.ToLowerInvariant().Replace(" ", "").Replace("_", "");
            if (ParameterNameMap.TryGetValue(normalizedInput, out string mappedName))
                return mappedName;
                
            // 如果沒有直接映射，返回原始輸入
            return input;
        }
        
        /// <summary>
        /// 從列表中找到最接近的字符串
        /// </summary>
        /// <param name="input">輸入字符串</param>
        /// <param name="candidates">候選字符串列表</param>
        /// <returns>最接近的字符串</returns>
        public static string FindClosestMatch(string input, IEnumerable<string> candidates)
        {
            if (string.IsNullOrWhiteSpace(input) || candidates == null || !candidates.Any())
                return input;
                
            // 首先嘗試精確匹配
            var exactMatch = candidates.FirstOrDefault(c => string.Equals(c, input, StringComparison.OrdinalIgnoreCase));
            if (exactMatch != null)
                return exactMatch;
                
            // 嘗試包含匹配
            var containsMatches = candidates.Where(c => c.IndexOf(input, StringComparison.OrdinalIgnoreCase) >= 0).ToList();
            if (containsMatches.Count == 1)
                return containsMatches[0];
                
            // 嘗試前綴匹配
            var prefixMatches = candidates.Where(c => c.StartsWith(input, StringComparison.OrdinalIgnoreCase)).ToList();
            if (prefixMatches.Count == 1)
                return prefixMatches[0];
                
            // 如果有多個匹配，返回最短的一個
            if (containsMatches.Any())
                return containsMatches.OrderBy(c => c.Length).First();
                
            // 如果沒有匹配，返回原始輸入
            return input;
        }
    }
}
