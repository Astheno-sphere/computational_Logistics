using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    /// <summary>
    /// Perform a boolean union on multiple objects.
    /// </summary>
    [McpCommand("boolean_union", SupportsDryRun = true)]
    public JObject BooleanUnion(JObject parameters)
    {
        var results = ComputeBooleanUnion(parameters, out var sourceObjects);

        if (parameters["dry_run"]?.ToObject<bool>() == true)
        {
            var message = $"Boolean union would create {results.Length} object(s)";
            if (results.Length == sourceObjects.Count)
                message += "; inputs do not intersect, so nothing would merge";
            return PredictBoolean(results, message);
        }

        var doc = RhinoDoc.ActiveDoc;
        var deleteSources = parameters["delete_sources"]?.ToObject<bool>() ?? true;
        var name = parameters["name"]?.ToString();

        // Delete source objects if requested
        if (deleteSources)
        {
            foreach (var obj in sourceObjects)
                doc.Objects.Delete(obj, true);
        }

        // Add result objects
        var resultIds = new JArray();
        foreach (var result in results)
        {
            var attr = new ObjectAttributes();
            if (!string.IsNullOrEmpty(name))
                attr.Name = name;

            var id = doc.Objects.AddBrep(result, attr);
            resultIds.Add(id.ToString());
        }

        doc.Views.Redraw();

        return new JObject
        {
            ["result_ids"] = resultIds,
            ["count"] = results.Length,
            ["message"] = $"Boolean union created {results.Length} object(s)"
        };
    }

    /// <summary>
    /// Perform a boolean difference (subtraction) operation.
    /// </summary>
    [McpCommand("boolean_difference", SupportsDryRun = true)]
    public JObject BooleanDifference(JObject parameters)
    {
        var results = ComputeBooleanDifference(parameters, out var baseObj, out var subtractObjects);

        if (parameters["dry_run"]?.ToObject<bool>() == true)
            return PredictBoolean(results, $"Boolean difference would create {results.Length} object(s)");

        var doc = RhinoDoc.ActiveDoc;
        var deleteSources = parameters["delete_sources"]?.ToObject<bool>() ?? true;
        var name = parameters["name"]?.ToString();

        // Delete source objects if requested
        if (deleteSources)
        {
            doc.Objects.Delete(baseObj, true);
            foreach (var obj in subtractObjects)
                doc.Objects.Delete(obj, true);
        }

        // Add result objects
        var resultIds = new JArray();
        foreach (var result in results)
        {
            var attr = new ObjectAttributes();
            if (!string.IsNullOrEmpty(name))
                attr.Name = name;

            var id = doc.Objects.AddBrep(result, attr);
            resultIds.Add(id.ToString());
        }

        doc.Views.Redraw();

        return new JObject
        {
            ["result_ids"] = resultIds,
            ["count"] = results.Length,
            ["message"] = $"Boolean difference created {results.Length} object(s)"
        };
    }

    /// <summary>
    /// Perform a boolean intersection operation.
    /// </summary>
    [McpCommand("boolean_intersection", SupportsDryRun = true)]
    public JObject BooleanIntersection(JObject parameters)
    {
        var results = ComputeBooleanIntersection(parameters, out var sourceObjects);

        if (parameters["dry_run"]?.ToObject<bool>() == true)
            return PredictBoolean(results, $"Boolean intersection would create {results.Length} object(s)");

        var doc = RhinoDoc.ActiveDoc;
        var deleteSources = parameters["delete_sources"]?.ToObject<bool>() ?? true;
        var name = parameters["name"]?.ToString();

        // Delete source objects if requested
        if (deleteSources)
        {
            foreach (var obj in sourceObjects)
                doc.Objects.Delete(obj, true);
        }

        // Add result objects
        var resultIds = new JArray();
        foreach (var result in results)
        {
            var attr = new ObjectAttributes();
            if (!string.IsNullOrEmpty(name))
                attr.Name = name;

            var id = doc.Objects.AddBrep(result, attr);
            resultIds.Add(id.ToString());
        }

        doc.Views.Redraw();

        return new JObject
        {
            ["result_ids"] = resultIds,
            ["count"] = results.Length,
            ["message"] = $"Boolean intersection created {results.Length} object(s)"
        };
    }

    /// <summary>
    /// Resolve the inputs and fuse them, returning the result Breps without
    /// touching the document. Shared by the real run and the dry_run preview.
    /// </summary>
    private Brep[] ComputeBooleanUnion(JObject parameters, out List<RhinoObject> sources)
    {
        var doc = RhinoDoc.ActiveDoc;
        var objectIds = parameters["object_ids"]?.ToObject<List<string>>();

        if (objectIds == null || objectIds.Count < 2)
            throw new ArgumentException("Boolean union requires at least 2 object IDs");

        var breps = new List<Brep>();
        sources = new List<RhinoObject>();

        foreach (var idStr in objectIds)
        {
            var obj = doc.Objects.Find(new Guid(idStr));
            if (obj == null)
                throw new InvalidOperationException($"Object with ID {idStr} not found");

            sources.Add(obj);
            var brep = GetBrepFromObject(obj);
            if (brep == null)
                throw new InvalidOperationException($"Object {idStr} is not a solid, surface, or extrusion and cannot be used in a boolean operation");
            breps.Add(brep);
        }

        if (breps.Count < 2)
            throw new InvalidOperationException("Could not extract valid Breps from the provided objects");

        var results = Brep.CreateBooleanUnion(breps, RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);

        if (results == null || results.Length == 0)
            throw new InvalidOperationException("Boolean union failed - objects may not intersect or be valid solids");

        return results;
    }

    /// <summary>
    /// Resolve the base and subtract inputs and carve them, returning the result
    /// Breps without touching the document. Shared by the real run and the dry_run
    /// preview; the base object comes back out for the caller's delete pass.
    /// </summary>
    private Brep[] ComputeBooleanDifference(JObject parameters, out RhinoObject baseObj, out List<RhinoObject> sources)
    {
        var doc = RhinoDoc.ActiveDoc;
        var baseId = parameters["base_id"]?.ToString();
        var subtractIds = parameters["subtract_ids"]?.ToObject<List<string>>();

        if (string.IsNullOrEmpty(baseId))
            throw new ArgumentException("Boolean difference requires a base_id");

        if (subtractIds == null || subtractIds.Count == 0)
            throw new ArgumentException("Boolean difference requires at least one subtract_id");

        baseObj = doc.Objects.Find(new Guid(baseId));
        if (baseObj == null)
            throw new InvalidOperationException($"Base object with ID {baseId} not found");

        var baseBreps = new List<Brep>();
        var baseBrep = GetBrepFromObject(baseObj);
        if (baseBrep != null)
            baseBreps.Add(baseBrep);
        else
            throw new InvalidOperationException("Could not extract valid Brep from base object");

        var subtractBreps = new List<Brep>();
        sources = new List<RhinoObject>();

        foreach (var idStr in subtractIds)
        {
            var obj = doc.Objects.Find(new Guid(idStr));
            if (obj == null)
                throw new InvalidOperationException($"Object with ID {idStr} not found");

            sources.Add(obj);
            var brep = GetBrepFromObject(obj);
            if (brep == null)
                throw new InvalidOperationException($"Object {idStr} is not a solid, surface, or extrusion and cannot be used in a boolean operation");
            subtractBreps.Add(brep);
        }

        if (subtractBreps.Count == 0)
            throw new InvalidOperationException("Could not extract valid Breps from subtract objects");

        var results = Brep.CreateBooleanDifference(baseBreps, subtractBreps, RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);

        if (results == null || results.Length == 0)
            throw new InvalidOperationException("Boolean difference failed - objects may not intersect or be valid solids");

        return results;
    }

    /// <summary>
    /// Resolve the inputs and intersect them, returning the result Breps without
    /// touching the document. Shared by the real run and the dry_run preview.
    /// </summary>
    private Brep[] ComputeBooleanIntersection(JObject parameters, out List<RhinoObject> sources)
    {
        var doc = RhinoDoc.ActiveDoc;
        var objectIds = parameters["object_ids"]?.ToObject<List<string>>();

        if (objectIds == null || objectIds.Count < 2)
            throw new ArgumentException("Boolean intersection requires at least 2 object IDs");

        var breps = new List<Brep>();
        sources = new List<RhinoObject>();

        foreach (var idStr in objectIds)
        {
            var obj = doc.Objects.Find(new Guid(idStr));
            if (obj == null)
                throw new InvalidOperationException($"Object with ID {idStr} not found");

            sources.Add(obj);
            var brep = GetBrepFromObject(obj);
            if (brep == null)
                throw new InvalidOperationException($"Object {idStr} is not a solid, surface, or extrusion and cannot be used in a boolean operation");
            breps.Add(brep);
        }

        if (breps.Count < 2)
            throw new InvalidOperationException("Could not extract valid Breps from the provided objects");

        var results = Brep.CreateBooleanIntersection(breps[0], breps[1], RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);

        // For more than 2 objects, chain intersections
        for (int i = 2; i < breps.Count && results != null && results.Length > 0; i++)
        {
            var newResults = new List<Brep>();
            foreach (var r in results)
            {
                var intersected = Brep.CreateBooleanIntersection(r, breps[i], RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);
                if (intersected != null)
                    newResults.AddRange(intersected);
            }
            results = newResults.ToArray();
        }

        if (results == null || results.Length == 0)
            throw new InvalidOperationException("Boolean intersection failed - objects may not intersect or be valid solids");

        return results;
    }

    /// <summary>
    /// Build the dry_run response: the metrics a real run would produce, derived
    /// from the in-memory result Breps, with no change to the document.
    /// </summary>
    private JObject PredictBoolean(Brep[] results, string message)
    {
        var predicted = new JArray();
        foreach (var brep in results)
            predicted.Add(DescribeResultBrep(brep));

        return new JObject
        {
            ["dry_run"] = true,
            ["would_succeed"] = true,
            ["count"] = results.Length,
            ["results"] = predicted,
            ["message"] = message
        };
    }

    private JObject DescribeResultBrep(Brep brep)
    {
        var valid = brep.IsValidWithLog(out var log);

        var info = new JObject { ["valid"] = valid };
        if (!valid)
            info["reason"] = log;

        info["is_solid"] = brep.IsSolid;

        // Volume is meaningful only for a closed solid; an open Brep still yields
        // a non-null (garbage) value, so gate on IsSolid rather than a null check.
        if (brep.IsSolid)
        {
            var volume = VolumeMassProperties.Compute(brep);
            if (volume != null)
                info["volume"] = volume.Volume;
        }

        var area = AreaMassProperties.Compute(brep);
        if (area != null)
            info["area"] = area.Area;

        info["bounding_box"] = Serializer.SerializeBBox(brep.GetBoundingBox(true));
        return info;
    }

    /// <summary>
    /// Helper to extract a Brep from various geometry types.
    /// </summary>
    private Brep GetBrepFromObject(RhinoObject obj)
    {
        if (obj.Geometry is Brep brep)
            return brep;

        if (obj.Geometry is Extrusion extrusion)
            return extrusion.ToBrep();

        if (obj.Geometry is Surface surface)
            return surface.ToBrep();

        return null;
    }
}
