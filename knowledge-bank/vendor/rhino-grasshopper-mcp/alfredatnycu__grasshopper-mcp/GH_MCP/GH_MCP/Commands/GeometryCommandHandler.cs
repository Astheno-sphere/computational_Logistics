using System;
using System.Collections.Generic;
using GrasshopperMCP.Models;
using Grasshopper.Kernel;
using Rhino.Geometry;
using Newtonsoft.Json.Linq;
using System.Linq;
using Rhino;

namespace GrasshopperMCP.Commands
{
    /// <summary>
    /// 處理幾何相關命令的處理器
    /// </summary>
    public static class GeometryCommandHandler
    {
        /// <summary>
        /// 創建點
        /// </summary>
        /// <param name="command">包含點坐標的命令</param>
        /// <returns>創建的點信息</returns>
        public static object CreatePoint(Command command)
        {
            double x = command.GetParameter<double>("x");
            double y = command.GetParameter<double>("y");
            double z = command.GetParameter<double>("z");
            
            // 創建點
            Point3d point = new Point3d(x, y, z);
            
            // 返回點信息
            return new
            {
                id = Guid.NewGuid().ToString(),
                x = point.X,
                y = point.Y,
                z = point.Z
            };
        }
        
        /// <summary>
        /// 創建曲線
        /// </summary>
        /// <param name="command">包含曲線點的命令</param>
        /// <returns>創建的曲線信息</returns>
        public static object CreateCurve(Command command)
        {
            var pointsData = command.GetParameter<JArray>("points");
            
            if (pointsData == null || pointsData.Count < 2)
            {
                throw new ArgumentException("At least 2 points are required to create a curve");
            }
            
            // 將 JSON 點數據轉換為 Point3d 列表
            List<Point3d> points = new List<Point3d>();
            foreach (var pointData in pointsData)
            {
                double x = pointData["x"].Value<double>();
                double y = pointData["y"].Value<double>();
                double z = pointData["z"]?.Value<double>() ?? 0.0;
                
                points.Add(new Point3d(x, y, z));
            }
            
            // 創建曲線
            Curve curve;
            if (points.Count == 2)
            {
                // 如果只有兩個點，創建一條直線
                curve = new LineCurve(points[0], points[1]);
            }
            else
            {
                // 如果有多個點，創建一條內插曲線
                curve = Curve.CreateInterpolatedCurve(points, 3);
            }
            
            // 返回曲線信息
            return new
            {
                id = Guid.NewGuid().ToString(),
                pointCount = points.Count,
                length = curve.GetLength()
            };
        }
        
        /// <summary>
        /// 創建圓
        /// </summary>
        /// <param name="command">包含圓心和半徑的命令</param>
        /// <returns>創建的圓信息</returns>
        public static object CreateCircle(Command command)
        {
            var centerData = command.GetParameter<JObject>("center");
            double radius = command.GetParameter<double>("radius");
            
            if (centerData == null)
            {
                throw new ArgumentException("Center point is required");
            }
            
            if (radius <= 0)
            {
                throw new ArgumentException("Radius must be greater than 0");
            }
            
            // 解析圓心
            double x = centerData["x"].Value<double>();
            double y = centerData["y"].Value<double>();
            double z = centerData["z"]?.Value<double>() ?? 0.0;
            
            Point3d center = new Point3d(x, y, z);
            
            // 創建圓
            Circle circle = new Circle(center, radius);
            
            // 返回圓信息
            return new
            {
                id = Guid.NewGuid().ToString(),
                center = new { x = center.X, y = center.Y, z = center.Z },
                radius = circle.Radius,
                circumference = circle.Circumference
            };
        }
    }
}
