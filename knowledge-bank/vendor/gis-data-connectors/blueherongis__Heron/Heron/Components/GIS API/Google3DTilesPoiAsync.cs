using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using GrasshopperAsyncComponent.Google;
using Heron.Utilities.Google3DTiles;
using Rhino;
using Rhino.Geometry;
using Rhino.Render.CustomRenderMeshes;
using Rhino.UI.Controls;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using SysEnv = System.Environment;


namespace Heron.Components.GIS_API
{
    public class Google3DTilesPoiAsync : GH_AsyncComponentGoogle<Google3DTilesPoiAsync>
    {
        public override Guid ComponentGuid => new Guid("93AE1A7A-1FA0-4DA0-B651-FEEA23F5DD16");

        protected override System.Drawing.Bitmap Icon => Properties.Resources.vector;

        public override GH_Exposure Exposure => GH_Exposure.quarternary;

        public Google3DTilesPoiAsync()
          : base("Google 3D Tiles POI Async", "G3DTilesPOIAsync",
              "Asynchronously fetches Points of Interest (POI) from Google 3D Tiles based on specified parameters.",
              "Heron", "GIS API")
        {
            BaseWorker = new Google3DTilesPoiWorker(this);
        }

        protected override void RegisterInputParams(GH_Component.GH_InputParamManager p)
        {

            // Order requested: POIs, Boundary, LOD, MaxSSE, K, Folder, API Key, Download
            string defaultCacheFolder;
            var rhinoDocPath = Rhino.RhinoDoc.ActiveDoc?.Path;
            if (!string.IsNullOrEmpty(rhinoDocPath))
            {
                var docDir = Path.GetDirectoryName(rhinoDocPath);
                defaultCacheFolder = Path.Combine(docDir, "Heron3DTilesCache");
            }
            else
            {
                defaultCacheFolder = Path.Combine(
                    SysEnv.GetFolderPath(SysEnv.SpecialFolder.LocalApplicationData),
                    "Heron3DTilesCache");
            }

            p.AddPointParameter("Point of Interest", "P", "Point of Interest (POI) to center LOD levels around. " +
                "Multiple points can be used to increase detail at multiple locations within the boundary.", GH_ParamAccess.list);
            p.AddCurveParameter("Boundary", "B", "Boundary (planar) in model coordinates (use Heron to place by lat/lon).", GH_ParamAccess.item);
            p.AddIntegerParameter("Level of Detail", "LOD", "Maximum Level of Detail (LOD) closest to the POI. 0 to 20, 20 = max.", GH_ParamAccess.item, 4);
            p.AddIntegerParameter("Max Screen Space Error", "E", "1 to 100, lower values results more detailed meshes closer to the POI.\r\n " +
                "Max Performance = 64\r\n " +
                "Mobile Default = 32\r\n " +
                "Standard = 16\r\n " +
                "High Fidelity = 8\r\n " +
                "Cinematic = 1 to 2", GH_ParamAccess.item, 16);
            p.AddIntegerParameter("Constant (K)", "C", "Constant K for POI influence on LOD (higher = more influence, min 100).  " +
                "K is essentially the conversion factor that defines how many pixels a 1-meter object occupies when it is exactly 1 meter away from the camera.\r\n " +
                "1080p at 60deg FOV ~= 935\r\n " +
                "4k at 60deg FOV ~= 1870\r\n " +
                "720p at 60deg FOV ~= 620\r\n " +
                "This component is not related to the Rhino viewports, so K needs to be set manually.", GH_ParamAccess.item, 600);
            p.AddTextParameter("Cache Folder", "Fp", "Folder path to store tile cache (.glb files).", GH_ParamAccess.item, defaultCacheFolder);
            p.AddTextParameter("API Key", "K", "Google Maps Platform API key. Or set an Environment Variable 'HERONGOOGLEAPIKEY' with your key as the string.", GH_ParamAccess.item, "");
            p.AddBooleanParameter("Run", "R", "If true, run and Download. If false, do nothing.", GH_ParamAccess.item, false);
        }

        protected override void RegisterOutputParams(GH_Component.GH_OutputParamManager p)
        {
            p.AddBoxParameter("Tile Bounding Boxes", "B", "Bounding boxes of the downloaded tiles in model coordinates.", GH_ParamAccess.list);
        }

        public override void AppendAdditionalMenuItems(ToolStripDropDown menu)
        {
            base.AppendAdditionalMenuItems(menu);
            Menu_AppendItem(
                menu,
                "Cancel",
                (s, e) =>
                {
                    RequestCancellation();
                }
            );
        }

        private sealed class Google3DTilesPoiWorker : WorkerInstanceGoogle<Google3DTilesPoiAsync>
        {
            private List<GH_Point> PoisGH { get; set; } = new List<GH_Point>();
            private List<Point3d> Pois { get; set; } = new List<Point3d>();
            private static PointCloud PoiPc { get; set; } = new PointCloud();
            private Curve Boundary { get; set; } = null;
            private Box AoiEcefBox { get; set; } = new Box();
            private static int MaxLod { get; set; } = 4;
            private static int MaxSse { get; set; } = 16;
            private static int K { get; set; } = 600;
            private string CacheFolder { get; set; } = null;
            private string ApiKey { get; set; } = null;
            private string SessionId { get; set; } = null;
            private bool Download { get; set; } = false;
            private Polyline Aoi { get; set; } = null;
            private List<Box> TileBoundingBoxes { get; set; } = new List<Box>();
            private List<Tile> DownloadedTiles { get; set; } = new List<Tile>();

            private static readonly HttpClient Client = new HttpClient();

            private double MinDistance { get; set; } = double.MaxValue;
            private readonly object SyncLock = new object();
            private int Depth { get; set; } = 0;

            public Google3DTilesPoiWorker(
                Google3DTilesPoiAsync parent,
                string id = "baseworker",
                CancellationToken cancellationToken = default) : base(parent, id, cancellationToken) { }

            public override async Task DoWork(Action<string, double> reportProgress, Action done)
            {
                try 
                {
                    if (Download)
                    {
                        await TilesetWalkerAsync(reportProgress);
                        done();
                    }
                }
                //catch (Exception ex)
                //{
                //    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, $"Error in Google 3D Tiles POI Worker: {ex.Message}");
                //    done();
                //    return Task.CompletedTask;
                //}
                catch (OperationCanceledException) when (CancellationToken.IsCancellationRequested)
                {
                    //No need to call `done()` - GrasshopperAsyncComponent assumes immediate cancel,
                    //thus it has already performed clean-up actions that would normally be done on `done()
                }
                await Task.CompletedTask;
            }

            public async Task TilesetWalkerAsync(Action<string, double> reportProgress)
            {
                // Check for cancellation
                CancellationToken.ThrowIfCancellationRequested();

                // Get Root URL & Session ID (Valid for ~3 hours)
                string rootUrl = $"https://tile.googleapis.com/v1/3dtiles/root.json?key={ApiKey}";

                var tileset = await Client.GetFromJsonAsync<Tileset>(rootUrl);
                if (tileset?.root != null)
                {
                    //var uri = tileset.root.Content.Uri;
                    //SessionId = ExtractSessionId(uri);
                    Console.WriteLine("Starting traversal toward Point of Interest...");
                    //await TraverseTileAsync(tileset.root, MaxSse, reportProgress);
                    await TraverseTileAsync2(tileset.root, MaxSse, reportProgress, CancellationToken);
                }
            }



            private async Task TraverseTileAsync(Tile tile, double maxSse, Action<string, double> reportProgress)
            {
                // 0. Cancellation
                CancellationToken.ThrowIfCancellationRequested();

                // 1. Compute distance and SSE
                var distance = CalculateDistanceToPOI(tile);
                double sse = (tile.GeometricError * K) / Math.Max(distance, 1.0);
                if (distance < MinDistance) MinDistance = distance;

                bool isleaf = (tile.Children == null || tile.Children.Count == 0) && !tile.Content.Uri.Contains(".json");

                // 2. If we need more refinement
                if ((sse > maxSse || tile.GeometricError == 0) && !isleaf)
                {
                    // 2a. If children are present, traverse them in parallel
                    if (tile.Children != null && tile.Children.Count > 0)
                    {
                        CancellationToken.ThrowIfCancellationRequested();
                        var tasks = tile.Children.Select(child => TraverseTileAsync(child, maxSse, reportProgress)).ToArray();
                        if (tasks.Length > 0)
                            await Task.WhenAll(tasks);
                    }
                    else
                    {
                        // 2b. No children loaded: attempt to fetch a child tileset or treat content as geometry
                        if (!string.IsNullOrEmpty(tile.Content?.Uri) && TileIntersectsAoi(tile))
                        {
                            CancellationToken.ThrowIfCancellationRequested();

                            // Build URL and ensure API key is appended
                            string childUrl = tile.Content.Uri.StartsWith("http", StringComparison.OrdinalIgnoreCase)
                                ? tile.Content.Uri
                                : $"https://tile.googleapis.com{tile.Content.Uri}";
                            if (!childUrl.Contains("key=") && !string.IsNullOrEmpty(ApiKey))
                                childUrl = $"{childUrl}{(childUrl.Contains("?") ? "&" : "?")}key={ApiKey}";

                            try
                            {
                                using (var response = await Client.GetAsync(childUrl, CancellationToken))
                                {
                                    if (!response.IsSuccessStatusCode)
                                    {
                                        Console.WriteLine($"Failed to fetch child tileset/content: {response.StatusCode} ({childUrl})");
                                        return;
                                    }

                                    var mediaType = response.Content.Headers.ContentType?.MediaType ?? string.Empty;
                                    // If JSON, treat as a tileset and parse children
                                    if (mediaType.IndexOf("json", StringComparison.OrdinalIgnoreCase) >= 0
                                        || childUrl.Contains(".json")
                                        || childUrl.IndexOf("tileset", StringComparison.OrdinalIgnoreCase) >= 0)
                                    {
                                        // Parse tileset JSON
                                        Tileset childTileset = null;
                                        try
                                        {
                                            childTileset = await response.Content.ReadFromJsonAsync<Tileset>(cancellationToken: CancellationToken);
                                        }
                                        catch (Exception ex)
                                        {
                                            Console.WriteLine($"Failed to parse child tileset JSON: {ex.Message}");
                                        }

                                        if (childTileset?.root != null && childTileset.root.Children != null && childTileset.root.Children.Count > 0)
                                        {
                                            CancellationToken.ThrowIfCancellationRequested();
                                            var tasks = childTileset.root.Children.Select(ct => TraverseTileAsync(ct, maxSse, reportProgress)).ToArray();
                                            if (tasks.Length > 0)
                                                await Task.WhenAll(tasks);
                                        }
                                    }
                                    else
                                    {
                                        // Non-JSON (likely binary glb/gltf): treat this tile as a downloadable geometry tile
                                        // Avoid duplicate adds
                                        lock (DownloadedTiles)
                                        {
                                            if (!DownloadedTiles.Contains(tile))
                                                DownloadedTiles.Add(tile);
                                        }
                                        reportProgress?.Invoke($"Tiles: {DownloadedTiles.Count}", DownloadedTiles.Count / 1000.0);
                                    }
                                }
                            }
                            catch (OperationCanceledException) when (CancellationToken.IsCancellationRequested)
                            {
                                // propagate cancellation
                                throw;
                            }
                            catch (Exception ex)
                            {
                                Console.WriteLine($"Error fetching child content: {ex.Message}");
                            }
                        }
                    }
                }
                else
                {
                    // 3. LOD sufficient - collect tile if it has content
                    if (!string.IsNullOrEmpty(tile.Content?.Uri))
                    {
                        lock (DownloadedTiles)
                        {
                            if (!DownloadedTiles.Contains(tile))
                                DownloadedTiles.Add(tile);
                        }
                        reportProgress?.Invoke($"Tiles: {DownloadedTiles.Count}", DownloadedTiles.Count / 1000.0);
                    }
                    else
                    {
                        // No content to download; it's a structural tile.
                        Console.WriteLine("Target LOD reached, but tile has no geometry content.");
                    }
                }
            }




            private async Task TraverseTileAsync2(Tile tile, double maxSse, Action<string, double> reportProgress, CancellationToken ct)
            {
                ct.ThrowIfCancellationRequested();

                double distance = CalculateDistanceToPOI(tile);
                //if (distance > 10000.0) return; // Distance-based pruning

                // K is typically ~1100 for 1080p; distance is clamped to 1.0 to avoid Infinity
                double sse = (tile.GeometricError * K) / Math.Max(distance, 1.0);

                bool hasChildren = tile.Children != null && tile.Children.Count > 0;
                bool isExternal = tile.Content?.Uri?.Contains(".json") ?? false;
                bool hasGeometry = !string.IsNullOrEmpty(tile.Content?.Uri) && !isExternal;
                bool intersectsAoi = TileIntersectsAoi(tile);

                // DECISION LOGIC: 
                // 1. If SSE is too high, we MUST refine to get better detail.
                // 2. If the tile is "Empty" (no geometry), we MUST refine to find actual data.
                // 3. If it's an external tileset link, we MUST refine to load the sub-tree.
                bool shouldRefine = (sse > maxSse || !hasGeometry || isExternal || tile.GeometricError == 0) && (hasChildren || isExternal);

                if (shouldRefine)
                {
                    if (hasChildren)
                    {
                        using (var semaphore = new SemaphoreSlim(8))
                        {
                            var tasks = tile.Children.Select(async child =>
                            {
                                await semaphore.WaitAsync(ct).ConfigureAwait(false);
                                try { await TraverseTileAsync2(child, maxSse, reportProgress, ct).ConfigureAwait(false); }
                                finally { semaphore.Release(); }
                            });
                            await Task.WhenAll(tasks).ConfigureAwait(false);
                        }
                    }
                    else if (isExternal)
                    {
                        await LoadAndTraverseExternalTileset(tile, maxSse, reportProgress, ct).ConfigureAwait(false);
                    }
                }
                else if (hasGeometry)
                {
                    // Only collect tiles that actually have renderable content
                    lock (DownloadedTiles)
                    {
                        if (!DownloadedTiles.Contains(tile))
                        {
                            DownloadedTiles.Add(tile);
                            reportProgress?.Invoke($"Tiles: {DownloadedTiles.Count}", DownloadedTiles.Count / 1000.0);
                        }
                    }
                }
            }

            private async Task LoadAndTraverseExternalTileset(Tile tile, double maxSse, Action<string, double> reportProgress, CancellationToken ct)
            {
                // 1. Build the child URL correctly
                string url = tile.Content.Uri.StartsWith("http")
                    ? tile.Content.Uri
                    : $"https://tile.googleapis.com{tile.Content.Uri}";

                // Append API Key if missing
                if (!url.Contains("key="))
                    url += $"{(url.Contains("?") ? "&" : "?")}key={ApiKey}";

                try
                {
                    // 2. Fetch the external tileset JSON
                    // Using ConfigureAwait(false) for .NET 4.8 best practices
                    var childTileset = await Client.GetFromJsonAsync<Tileset>(url, ct).ConfigureAwait(false);

                    lock (SyncLock)
                    {
                        Depth++;
                    }

                    if (childTileset?.root != null)
                    {
                        // 3. CRITICAL: Restart traversal at the NEW root.
                        // Do not jump to childTileset.root.Children; the root itself may 
                        // have content or high SSE that requires further refinement.
                        await TraverseTileAsync2(childTileset.root, maxSse, reportProgress, ct).ConfigureAwait(false);
                    }
                }
                catch (Exception ex) when (!(ex is OperationCanceledException))
                {
                    Console.WriteLine($"Error fetching external tileset {url}: {ex.Message}");
                }
            }



            private string ExtractSessionId(string uri)
            {
                // Example URI: /v1/3dtiles/datasets/.../root.json?session=ABC123XYZ
                var match = System.Text.RegularExpressions.Regex.Match(uri, @"session=([^&]+)");
                return match.Groups[1].Value;
            }

            private async Task<byte[]> DownloadGeometryAsync(string tileUrl)
            {
                try
                {
                    // 1. Ensure the URL includes the mandatory API key
                    // Google's relative URIs usually already contain the ?session=ID
                    if (!tileUrl.Contains("key="))
                    {
                        tileUrl += $"&key={ApiKey}";
                    }

                    // 2. Perform the async GET request
                    HttpResponseMessage response = await Client.GetAsync(tileUrl);

                    // 3. Check for success (Handle 403 for expired sessions or 404 for missing tiles)
                    if (!response.IsSuccessStatusCode)
                    {
                        Console.WriteLine($"Error downloading tile: {response.StatusCode}");
                        return null;
                    }

                    // 4. Read the glTF/GLB payload as a byte array
                    byte[] geometryData = await response.Content.ReadAsByteArrayAsync();

                    Console.WriteLine($"Downloaded {geometryData.Length / 1024} KB of geometry.");

                    // 5. In a real app, you would pass this to your 3D loader here
                    // ParseAndDisplay(geometryData);

                    return geometryData;
                }
                catch (HttpRequestException ex)
                {
                    Console.WriteLine($"Network error during tile download: {ex.Message}");
                    return null;
                }
            }

            private double CalculateDistanceToPOI(Tile tile)
            {
                var tileBox = tile.GetEcefBox().Value;
                var mesh = Mesh.CreateFromBox(tileBox, 1, 1, 1);

                var bv = tile.BoundingVolume?.Box;
                var center = new Point3d(bv[0], bv[1], bv[2]);

                if (!tileBox.IsValid)
                    return (double.MaxValue);
                else
                {
                    var distance = double.MaxValue;
                    foreach (var pt in PoiPc)
                    {
                        var cp = tileBox.ClosestPoint(pt.Location);
                        var d = cp.DistanceTo(pt.Location);
                        if (d < distance) distance = d;
                    }
                    //if (distance == 0) distance = double.MaxValue; // Account for the closest point inside the tileBox is itself, distance = 0
                    return distance;
                }
                /*
                if (center == null)
                    return (double.MaxValue);
                else
                {
                    var cp = PoiPc.ClosestPoint(center);
                    var cpLocation = PoiPc[cp].Location;
                    var distance = cpLocation.DistanceTo(center);
                    return distance;
                }
                */
            }



            private double CalculateDistanceToPOI2(Tile tile)
            {
                var bv = tile.BoundingVolume?.Box;
                if (bv == null || bv.Length < 12) return double.MaxValue;

                // 1. Center of the box
                var center = new Point3d(bv[0], bv[1], bv[2]);

                // 2. Extract the three half-axes (vectors)
                var axisX = new Point3d(bv[3], bv[4], bv[5]);
                var axisY = new Point3d(bv[6], bv[7], bv[8]);
                var axisZ = new Point3d(bv[9], bv[10], bv[11]);

                // 3. Get the POI position (assuming PoiPc is your point cloud)
                var cp = PoiPc.ClosestPoint(center);
                var target = PoiPc[cp].Location;

                // 4. Calculate the vector from box center to target
                var offset = new Point3d(target.X - center.X, target.Y - center.Y, target.Z - center.Z);

                // 5. Project the offset onto each unit axis to find the distance along that axis
                double distSq = 0.0;

                distSq += CalcAxisDistanceSq(offset, axisX);
                distSq += CalcAxisDistanceSq(offset, axisY);
                distSq += CalcAxisDistanceSq(offset, axisZ);
                var distance = Math.Sqrt(distSq);
                return Math.Sqrt(distSq);
            }

            private double CalcAxisDistanceSq(Point3d offset, Point3d axis)
            {
                // The length of the axis vector is the "half-length" of the box in that direction
                double halfLength = Math.Sqrt(axis.X * axis.X + axis.Y * axis.Y + axis.Z * axis.Z);
                if (halfLength < 0.0001) return 0.0;

                // Unit vector for this axis
                double ux = axis.X / halfLength;
                double uy = axis.Y / halfLength;
                double uz = axis.Z / halfLength;

                // Project the center-to-POI offset onto this unit axis
                double projection = offset.X * ux + offset.Y * uy + offset.Z * uz;

                // Calculate how far the point is OUTSIDE the box along this axis
                double distance = 0.0;
                if (projection > halfLength) distance = projection - halfLength;
                else if (projection < -halfLength) distance = -halfLength - projection;

                return distance * distance;
            }



            private bool TileIntersectsAoi(Tile tile)
            {
                var obbBox = tile.GetEcefBox();
                if (obbBox == null)
                    return false;
                else
                {
                    return IntersectsObbAoiEcefBox(obbBox.Value);
                }
            }

            private Box GetAoiEcefBox(Point3d aoiEcefCenter, Point3d aoiEcefMin, Point3d aoiEcefMax)
            {
                var latLonHeightCenter = GeoUtils.EcefToWgs84Gdal(aoiEcefCenter);

                // Create plane for box
                var ecefPlaneXAxis = GeoUtils.Wgs84ToEcefGdal(latLonHeightCenter.lonDeg, latLonHeightCenter.latDeg + 1, latLonHeightCenter.h);
                var ecefPlaneYAxis = GeoUtils.Wgs84ToEcefGdal(latLonHeightCenter.lonDeg + 1, latLonHeightCenter.latDeg, latLonHeightCenter.h);
                var ecefPlane = new Plane(aoiEcefCenter, ecefPlaneXAxis, ecefPlaneYAxis);

                var ecefBox = new Box(ecefPlane, new List<Point3d>() {aoiEcefMin, aoiEcefMax});

                // Inflate increments in model units. 
                // Set Z to 10,000 meters. Mt. Everest is 8,849 meters.
                var activeDoc = RhinoDoc.ActiveDoc;
                if (activeDoc == null)
                    throw new Exception("Active Rhino document required for EarthAnchorPoint conversion.");
                double unitScaleModelToMeters = Rhino.RhinoMath.UnitScale(activeDoc.ModelUnitSystem, UnitSystem.Meters);

                ecefBox.Inflate(0, 0, 10000 / unitScaleModelToMeters);

                return ecefBox;
            }

            private bool IntersectsObbAoiEcefBox(Box obbBox)
            {
                // 1. Get the 3 primary axes for both boxes
                var axesA = new[] { AoiEcefBox.Plane.XAxis, AoiEcefBox.Plane.YAxis, AoiEcefBox.Plane.ZAxis };
                var axesB = new[] { obbBox.Plane.XAxis, obbBox.Plane.YAxis, obbBox.Plane.ZAxis };

                // 2. Get the 8 corners for both boxes
                var cornersA = AoiEcefBox.GetCorners();
                var cornersB = obbBox.GetCorners();

                // 3. Check all axes from Box A
                foreach (var axis in axesA)
                {
                    if (IsSeparatingAxis(cornersA, cornersB, axis)) return false;
                }

                // 4. Check all axes from Box B
                foreach (var axis in axesB)
                {
                    if (IsSeparatingAxis(cornersA, cornersB, axis)) return false;
                }

                // Note: A full 3D SAT implementation for boxes also requires checking
                // 9 cross-product axes for edge-edge collisions, but the above 6
                // are often sufficient for simple checks or as a quick-exit broad-phase test.

                // If no separating axis was found, they are NOT disjoint (they overlap)
                return true;


                /*
                // Full 3D SAT implementation for OBB-OBB intersection
                // --- Phase 1 & 2: Check the 6 primary axes ---
                foreach (var axis in axesA.Concat(axesB)) // Concat axes from both boxes
                {
                    // Must ensure axis is valid and normalized before use
                    if (axis.SquareLength < 1e-6) continue;
                    axis.Unitize();
                    if (IsSeparatingAxis(cornersA, cornersB, axis)) return false;
                }

                // --- Phase 3: Check the 9 cross-product axes (edge-edge checks) ---
                foreach (var axisA in axesA)
                {
                    foreach (var axisB in axesB)
                    {
                        // Calculate the cross product of two edge directions
                        Vector3d edgeCrossAxis = Vector3d.CrossProduct(axisA, axisB);

                        // If axes are parallel or nearly parallel, the cross product is near zero, skip it
                        if (edgeCrossAxis.SquareLength < 1e-6) continue;

                        edgeCrossAxis.Unitize();

                        if (IsSeparatingAxis(cornersA, cornersB, edgeCrossAxis)) return false;
                    }
                }

                // If we passed all 15 tests, no separating axis was found, so they are not disjoint (they overlap)
                return true;
                */
            }

            // Helper function to project points onto an axis and check for a gap
            private static bool IsSeparatingAxis(Point3d[] cornersA, Point3d[] cornersB, Vector3d axis)
            {
                double minA = double.MaxValue, maxA = double.MinValue;
                double minB = double.MaxValue, maxB = double.MinValue;

                foreach (var p in cornersA)
                {
                    // Projection is the dot product
                    double projection = (Vector3d)p * axis;
                    minA = Math.Min(minA, projection);
                    maxA = Math.Max(maxA, projection);
                }

                foreach (var p in cornersB)
                {
                    double projection = (Vector3d)p * axis;
                    minB = Math.Min(minB, projection);
                    maxB = Math.Max(maxB, projection);
                }

                // Check if the 1D intervals [minA, maxA] and [minB, maxB] have a gap
                // If MaxA < MinB or MaxB < MinA, there is a gap (they are disjoint along this axis)
                return maxA < minB || maxB < minA;
            }

            private Point3d FlipXY(Point3d pt)
            {
                return new Point3d(pt.Y, pt.X, pt.Z);
            }
            public override WorkerInstanceGoogle<Google3DTilesPoiAsync> Duplicate(
                string id, 
                CancellationToken cancellationToken) => new Google3DTilesPoiWorker(Parent, id, cancellationToken);

            public override void GetData(IGH_DataAccess da, GH_ComponentParamServer parameters)
            {                
                var doc = RhinoDoc.ActiveDoc;
                double modelTol = doc != null ? doc.ModelAbsoluteTolerance : 0.01;

                // Set up GDAL/OGR
                Heron.GdalConfiguration.ConfigureGdal();

                // Make sure global HeronSRS is being used.
                GeoUtils.SetSpatialReferences();

                List<GH_Point> poisGH = new List<GH_Point>(); // Allow for null point values
                List<Point3d> pois = new List<Point3d>();
                PointCloud poiPc = new PointCloud();
                Curve boundary = null;
                int maxLod = 4;
                int maxSse = 16;
                int k = 600;
                string cacheFolder = null;
                string apiKey = null;
                bool download = false;

                // Order requested: POIs, Boundary, LOD, MaxSSE, K, Folder, API Key, Download
                da.GetDataList(0, poisGH);
                if (!da.GetData(1, ref boundary) || boundary == null)
                {
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Boundary is required.");
                    return;
                }

                // Early bounding box validity check like other components
                var rawBBox = boundary.GetBoundingBox(true);
                if (!rawBBox.IsValid || rawBBox.Diagonal.Length <= modelTol)
                {
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Boundary bounding box invalid or too small.");
                    return;
                }

                da.GetData(2, ref maxLod);
                da.GetData(3, ref maxSse);
                da.GetData(4, ref k);
                da.GetData(5, ref cacheFolder);
                if (!da.GetData(6, ref apiKey) || string.IsNullOrWhiteSpace(apiKey))
                {
                    var envKey = System.Environment.GetEnvironmentVariable("HERONGOOGLEAPIKEY");
                    if (envKey is string && !string.IsNullOrWhiteSpace(envKey))
                    {
                        Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "Using HERONGOOGLEAPIKEY from Environmental Variables.");
                        apiKey = envKey;
                    }
                    else
                    {
                        Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "API Key is required.");
                        return;
                    }
                }
                da.GetData(7, ref download);

                for (int i = 0; i < poisGH.Count; i++)
                {
                    if (poisGH[i] != null)
                    {
                        var ptModel = poisGH[i].Value;
                        var ptEcef = GeoUtils.ModelToEcefPoint(ptModel);
                        //pois.Add(poisGH[i].Value);
                        poiPc.Add(ptEcef);
                    }
                    else
                    {
                        Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Invalid Point of Interest at index " + i);
                        return;
                    }
                }
                if (!boundary.TryGetPlane(out var boundaryPlane))
                {
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Boundary must be planar.");
                    return;
                }
                // Create AOI polyline *before* computing manifest metrics to ensure consistency
                var aoi = GeoUtils.GetAoiBoundingPolyline(boundary);

                if (aoi == null || !aoi.IsClosed)
                {
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Boundary must be a closed planar curve.");
                    return;
                }
                var aoiEcefBoxCenter = GeoUtils.ModelToEcefPoint(aoi.CenterPoint());
                var aoiEcefBoxMin = GeoUtils.ModelToEcefPoint(aoi[0]);
                var aoiEcefBoxMax = GeoUtils.ModelToEcefPoint(aoi[2]);
                AoiEcefBox = GetAoiEcefBox(aoiEcefBoxCenter, aoiEcefBoxMin, aoiEcefBoxMax);

                if (maxLod < 0)
                {
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Max LOD must be >= 0.");
                    return;
                }
                if (maxSse < 1)
                {
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Max Screen Space Error must be >= 1.");
                    return;
                }
                if (k < 1)
                {
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Constant K must be >= 1.");
                    return;
                }
                if (string.IsNullOrWhiteSpace(cacheFolder))
                {
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Cache Folder is required.");
                    return;
                }

                if (!Directory.Exists(cacheFolder)) Directory.CreateDirectory(cacheFolder);


                PoisGH = poisGH;
                Pois = pois;
                PoiPc = poiPc;
                Boundary = boundary;
                Aoi = aoi;
                MaxLod = maxLod;
                MaxSse = maxSse;
                K = k;
                CacheFolder = cacheFolder;
                ApiKey = apiKey;
                Download = download;

            }

            public override void SetData(IGH_DataAccess da)
            {           
                if (DownloadedTiles != null && DownloadedTiles.Count > 0)
                {
                    List<GH_Box> ghBoxes = new List<GH_Box>();
                    ghBoxes.Add(new GH_Box(AoiEcefBox));
                    foreach (var tile in DownloadedTiles)
                    {

                        ghBoxes.Add(new GH_Box(tile.GetEcefBox().Value));
                    }
                    da.SetDataList(0, ghBoxes);
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "Min Distance: " + MinDistance);
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "Depth: " + Depth);
                }
                else
                {
                    Parent.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "No tile bounding boxes set.");
                }
            }
        }
    }

    // Minimal Data Models for 2025 OGC glTF standard
    public class Tileset { public Tile root { get; set; } }
    public class Tile
    {
        public double GeometricError { get; set; }
        public BoundingVolume BoundingVolume { get; set; }
        public Content Content { get; set; }
        public List<Tile> Children { get; set; }

        /// <summary>
        /// Convert this tile's bounding volume "box" (12-double array per 3D Tiles spec)
        /// into a Rhino.Geometry.Box (or null if not available/invalid).
        /// Expected format: [center.x, center.y, center.z, ux,uy,uz, vx,vy,vz, wx,wy,wz]
        /// where ux/uy/uz etc. are the oriented half-axes vectors.
        /// </summary>
        public Rhino.Geometry.Box? GetEcefBox()
        {
            var boxArray = BoundingVolume?.Box;
            if (boxArray == null || boxArray.Length < 12)
                return null;

            // center
            var center = new Rhino.Geometry.Point3d(boxArray[0], boxArray[1], boxArray[2]);

            // axis vectors (these represent oriented half-axes; use their lengths as extents)
            var xDir = new Rhino.Geometry.Vector3d(boxArray[3], boxArray[4], boxArray[5]);
            var yDir = new Rhino.Geometry.Vector3d(boxArray[6], boxArray[7], boxArray[8]);
            var zDir = new Rhino.Geometry.Vector3d(boxArray[9], boxArray[10], boxArray[11]);

            // Create intervals based on axis lengths (symmetric around center)
            var xInterval = new Rhino.Geometry.Interval(-xDir.Length, xDir.Length);
            var yInterval = new Rhino.Geometry.Interval(-yDir.Length, yDir.Length);
            var zInterval = new Rhino.Geometry.Interval(-zDir.Length, zDir.Length);

            // Construct a plane from center using x and y axis directions for orientation.
            // If xDir or yDir are degenerate, fallback to world XY.
            Rhino.Geometry.Plane plane;
            if (!new Rhino.Geometry.Plane(center, xDir, yDir).IsValid)
                plane = new Rhino.Geometry.Plane(center, Rhino.Geometry.Vector3d.XAxis, Rhino.Geometry.Vector3d.YAxis);
            else
                plane = new Rhino.Geometry.Plane(center, xDir, yDir);

            return new Rhino.Geometry.Box(plane, xInterval, yInterval, zInterval);
        }
        public Rhino.Geometry.Box? GetModelBox()
        {
            var boxArray = BoundingVolume?.Box;
            if (boxArray == null || boxArray.Length < 12)
                return null;

            // center
            var center = GeoUtils.EcefToModelPoint(new Rhino.Geometry.Point3d(boxArray[0], boxArray[1], boxArray[2]));

            // axis vectors (these represent oriented half-axes; use their lengths as extents)
            var xDir = (Vector3d) GeoUtils.EcefToModelPoint(new Rhino.Geometry.Point3d(boxArray[3], boxArray[4], boxArray[5]));
            var yDir = (Vector3d) GeoUtils.EcefToModelPoint(new Rhino.Geometry.Point3d(boxArray[6], boxArray[7], boxArray[8]));
            var zDir = (Vector3d) GeoUtils.EcefToModelPoint(new Rhino.Geometry.Point3d(boxArray[9], boxArray[10], boxArray[11]));

            // Create intervals based on axis lengths (symmetric around center)
            var xInterval = new Rhino.Geometry.Interval(-xDir.Length, xDir.Length);
            var yInterval = new Rhino.Geometry.Interval(-yDir.Length, yDir.Length);
            var zInterval = new Rhino.Geometry.Interval(-zDir.Length, zDir.Length);

            // Construct a plane from center using x and y axis directions for orientation.
            // If xDir or yDir are degenerate, fallback to world XY.
            Rhino.Geometry.Plane plane;
            if (!new Rhino.Geometry.Plane(center, xDir, yDir).IsValid)
                plane = new Rhino.Geometry.Plane(center, Rhino.Geometry.Vector3d.XAxis, Rhino.Geometry.Vector3d.YAxis);
            else
                plane = new Rhino.Geometry.Plane(center, xDir, yDir);

            return new Rhino.Geometry.Box(plane, xInterval, yInterval, zInterval);
        }
    }
    public class BoundingVolume 
    { 
        public double[] Box { get; set; } 
    }

    public class Content { public string Uri { get; set; } }

    public class Refine
    {
        public const string ADD = "ADD";
        public const string REPLACE = "REPLACE";
    }
}