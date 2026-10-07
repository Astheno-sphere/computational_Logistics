using System;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using System.Text;
using System.Security.Cryptography;
using Grasshopper.Kernel;
using Heron.Utilities.Google3DTiles;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;
using SysEnv = System.Environment;
using GH_IO.Serialization;
using Rhino.Input; // For RhinoGet
using Rhino.Commands; // For Result
using Newtonsoft.Json;
using OSGeo.OSR;
using Grasshopper.Kernel.Types; // Manifest serialization

namespace Heron
{
    public class Google3DTilesPoi : HeronComponent
    {
        // Progress tracking
        private bool isDownloading = false;
        private int totalTiles = 0;
        private int downloadedTiles = 0;
        private long downloadedBytes = 0;

        // Component options (previously dynamic inputs)
        private bool clearCacheOption = false;
        private double maxSizeGbOption = 1.0; // soft cap in GB

        private const string ManifestPrefix = "manifest_"; // manifest_{hash}.json

        public Google3DTilesPoi()
          : base("Google 3D Tiles POI (Photorealistic)",
                 "G3DTilesPoi",
                 "Download + cache Google Photorealistic 3D Tiles from a POI (Point of Interest) within a boundary and import as meshes aligned to EarthAnchorPoint.  " +
                "Multiple points of interest can be used.  The detail of the meshes will fall off the farther they are from a POI.  " +
                "Adjust the Max Screen Space Error and Constant (k) to balance the levels of detail around POIs.  " +
                "The maximum level of detail to be reached at a POI is set with LOD.",
                 "GIS API")
        { }

        public override Grasshopper.Kernel.GH_Exposure Exposure
        {
            get { return GH_Exposure.quarternary; }
        }

        protected override System.Drawing.Bitmap Icon => Properties.Resources.shp;
        public override Guid ComponentGuid => new Guid("8C543C55-4CA4-4AC7-98C9-E04A839A1A31");

        protected override void RegisterInputParams(GH_InputParamManager p)
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

        protected override void RegisterOutputParams(GH_OutputParamManager p)
        {
            // Order requested: Info, Files, Meshes, Materials, Attribution, Logo
            p.AddTextParameter("Info", "I", "Status messages / diagnostics.", GH_ParamAccess.list);
            p.AddTextParameter("Files", "F", "Tile .glb files used (cache paths).", GH_ParamAccess.list);
            p.AddMeshParameter("Meshes", "M", "Imported meshes, oriented to EarthAnchorPoint.", GH_ParamAccess.list);
            p.AddGenericParameter("Materials", "Mat", "Materials for each tile.", GH_ParamAccess.list);
            p.AddTextParameter("Attribution", "A", "Google copyright/attribution text from tileset. Display this with the Google Maps logo.", GH_ParamAccess.item);
            p.AddGenericParameter("Google Logo", "Logo", "Google Maps logo bitmap. Must be displayed with attribution per Google's policy.", GH_ParamAccess.item);
        }

        // Context menu for options
        protected override void AppendAdditionalComponentMenuItems(System.Windows.Forms.ToolStripDropDown menu)
        {
            base.AppendAdditionalComponentMenuItems(menu);
            Menu_AppendSeparator(menu);

            Menu_AppendItem(menu,
                $"Clear Cache Before Download: {(clearCacheOption ? "On" : "Off")}",
                (s, e) => { clearCacheOption = !clearCacheOption; ExpireSolution(true); },
                true,
                clearCacheOption);

            var maxSizeRoot = Menu_AppendItem(menu, $"Max Size (GB): {maxSizeGbOption:0.##}");
            double[] presets = { 0.25, 0.5, 1, 2, 4, 8 };
            foreach (var preset in presets)
            {
                Menu_AppendItem(maxSizeRoot.DropDown,
                    preset.ToString("0.##"),
                    (s, e) => { maxSizeGbOption = preset; ExpireSolution(true); },
                    true,
                    Math.Abs(maxSizeGbOption - preset) < 1e-6);
            }
            Menu_AppendItem(maxSizeRoot.DropDown, "Custom...", (s, e) =>
            {
                double current = maxSizeGbOption;
                var rc = RhinoGet.GetNumber("Enter max size in GB", false, ref current, 0.01, 2048.0);
                if (rc == Result.Success)
                {
                    maxSizeGbOption = current;
                    ExpireSolution(true);
                }
            });
        }

        public override bool Write(GH_IWriter writer)
        {
            writer.SetBoolean("ClearCacheOption", clearCacheOption);
            writer.SetDouble("MaxSizeGbOption", maxSizeGbOption);
            return base.Write(writer);
        }

        public override bool Read(GH_IReader reader)
        {
            if (reader.ItemExists("ClearCacheOption")) clearCacheOption = reader.GetBoolean("ClearCacheOption");
            if (reader.ItemExists("MaxSizeGbOption")) maxSizeGbOption = reader.GetDouble("MaxSizeGbOption");
            return base.Read(reader);
        }

        protected override void SolveInstance(IGH_DataAccess da)
        {
            var doc = RhinoDoc.ActiveDoc;
            double modelTol = doc != null ? doc.ModelAbsoluteTolerance : 0.01;

            // Set up GDAL/OGR
            Heron.GdalConfiguration.ConfigureGdal();

            // Make sure global HeronSRS is being used.
            GeoUtils.SetSpatialReferences();

            List<GH_Point> poisGH = new List<GH_Point>(); // Allow for null point values
            List<Point3d> pois = new List<Point3d>();
            Curve boundary = null;
            int maxLod = 4;
            int maxSse = 16;
            int k = 600;
            string cacheFolder = null;
            string apiKey = null;
            bool download = false;

            // Inputs: 0 Pois, 1 Boundary, 2 Lod, 3 MaxSSE, 4 Constant (k), 5 Folder, 6 Key, 7 Download
            if (!da.GetDataList(0, poisGH))
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Point of Interest is required.");
                SetOutputs(da, new List<string> { "Error: Point of Interest is required." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }

            if (!da.GetData(1, ref boundary) || boundary == null)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Boundary is required.");
                SetOutputs(da, new List<string> { "Error: Boundary is required." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }

            // Early bounding box validity check like other components
            var rawBBox = boundary.GetBoundingBox(true);
            if (!rawBBox.IsValid || rawBBox.Diagonal.Length <= modelTol)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Boundary bounding box invalid or too small.");
                SetOutputs(da, new List<string> { "Error: Invalid / tiny boundary." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
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
                    AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "Using HERONGOOGLEAPIKEY from Environmental Variables.");
                    apiKey = envKey;
                }
                else
                {
                    AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "API Key is required.");
                    SetOutputs(da, new List<string> { "Error: API Key is required." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                    return;
                }
            }
            da.GetData(7, ref download);

            for (int i = 0; i < poisGH.Count; i++)
            {
                if (poisGH[i] != null)
                {
                    pois.Add(poisGH[i].Value);
                }
                else
                {
                    AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Invalid Point of Interest at index " + i);
                    SetOutputs(da, new List<string> { "Error: Invalid Point of Interest at index " + i }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                    return;
                }
            }

            if (!boundary.TryGetPlane(out var boundaryPlane))
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Boundary must be planar.");
                SetOutputs(da, new List<string> { "Error: Boundary must be planar." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }
            if (maxLod < 0)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Max LOD must be >= 0.");
                SetOutputs(da, new List<string> { "Error: Max LOD must be >= 0." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }
            if (maxSse < 1)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Max Screen Space Error must be >= 1.");
                SetOutputs(da, new List<string> { "Error: Max Screen Space Error must be >= 1." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }
            if (k < 1)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Constant K must be >= 1.");
                SetOutputs(da, new List<string> { "Error: Constant K must be >= 1." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }
            if (string.IsNullOrWhiteSpace(cacheFolder))
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Cache Folder is required.");
                SetOutputs(da, new List<string> { "Error: Cache Folder is required." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }
            if (maxSizeGbOption < 0.0)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Max Size (GB) option must be >= 0.");
                SetOutputs(da, new List<string> { "Error: Max Size (GB) option must be >= 0." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }

            if (!Directory.Exists(cacheFolder)) Directory.CreateDirectory(cacheFolder);

            // Create AOI polyline *before* computing manifest metrics to ensure consistency
            var aoi = GeoUtils.GetAoiBoundingPolyline(boundary);

            if (aoi == null || !aoi.IsClosed)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Boundary must be a closed planar curve.");
                SetOutputs(da, new List<string> { "Error: Boundary must be a closed planar curve." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }
            var aoiBounds = aoi.BoundingBox;

            // WGS84 AOI bounds for Manifest
            double minLon = 0, minLat = 0, maxLon = 0, maxLat = 0;
            try
            {
                var wgs = GeoUtils.AoiToWgs(aoi);
                minLon = wgs.minLon; minLat = wgs.minLat; maxLon = wgs.maxLon; maxLat = wgs.maxLat;
            }
            catch (Exception exWgsBounds)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Failed WGS84 bounds: " + exWgsBounds.Message);
            }

            var aoiPoiForHash = aoi;
            aoiPoiForHash.Remove(aoiPoiForHash.Last);
            foreach (var pt in pois) aoiPoiForHash.Add(pt);
            string wgsVertexHash = ComputeWgsVertexHash(aoiPoiForHash);
            string boundaryHash = ComputeBoundaryHash(aoiPoiForHash.ToNurbsCurve(), maxLod); // model-space hash retained
            string manifestPath = Path.Combine(cacheFolder, ManifestPrefix + boundaryHash + ".json");

            // Cache clearing option
            if (download && clearCacheOption)
            {
                try
                {
                    Message = "Clearing cache...";
                    Grasshopper.Instances.RedrawCanvas();

                    // Delete tile files
                    foreach (var f in Directory.EnumerateFiles(cacheFolder, "*.glb"))
                    {
                        try { File.Delete(f); } catch { }
                    }

                    // Delete manifest files
                    foreach (var mf in Directory.EnumerateFiles(cacheFolder, ManifestPrefix + "*.json"))
                    {
                        try { File.Delete(mf); } catch { }
                    }

                    // Delete consolidated metadata file
                    var metadataFile = Path.Combine(cacheFolder, "tiles_cache_metadata.json");
                    if (File.Exists(metadataFile))
                    {
                        try { File.Delete(metadataFile); } catch { }
                    }
                }
                catch (Exception ex)
                {
                    AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Failed to clear cache: " + ex.Message);
                }
            }
            else if (!download && clearCacheOption)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "Clear Cache option ignored because Download is false.");
            }

            var activeDoc = RhinoDoc.ActiveDoc;
            if (activeDoc == null)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "No active Rhino document.");
                SetOutputs(da, new List<string> { "Error: No active Rhino document." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }
            var eap = activeDoc.EarthAnchorPoint;
            if (eap == null || !eap.EarthLocationIsSet())
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "EarthAnchorPoint not set.");
                SetOutputs(da, new List<string> { "Error: EarthAnchorPoint not set." }, new List<string>(), new List<Rhino.Geometry.Mesh>(), new List<object>(), string.Empty);
                return;
            }

            var info = new List<string>();
            var usedFiles = new List<string>();
            string attribution = string.Empty; // Store attribution from root tileset

            // Try manifest first (works both when download=false and download=true) to avoid traversal when valid
            ManifestData manifestData;
            Message = "Verifying manifest...";
            Grasshopper.Instances.RedrawCanvas();
            info.Add("Verifying manifest for boundary hash: " + boundaryHash);
            double matchTolModel = Math.Max(modelTol * 2.0, 0.01);
            double matchTolDeg = 1e-5; // ~1 meter
            bool manifestValid = TryLoadManifest(manifestPath, out manifestData) && NewBoundaryMatches(manifestData, aoiBounds, matchTolModel, minLon, minLat, maxLon, maxLat, matchTolDeg, wgsVertexHash, maxLod);

            if (manifestValid)
            {
                info.Add("Manifest found: " + Path.GetFileName(manifestPath));

                // VALIDATE CACHE EXPIRATION
                var api = new GoogleTilesApi(apiKey, cacheFolder);
                ValidateCachedTiles(api, manifestPath, info);

                var manifestTilePaths = manifestData.Tiles.Select(t => Path.Combine(cacheFolder, t.File)).ToList();
                bool allExist = manifestTilePaths.All(File.Exists);

                // Extract attribution from manifest if available
                if (!string.IsNullOrEmpty(manifestData.Attribution))
                {
                    attribution = manifestData.Attribution;
                }

                if (!allExist)
                {
                    info.Add("Manifest tiles missing - proceeding with traversal.");
                }
                else if (!download)
                {
                    info.Add("All cached tiles are present and will be loaded from cache when Run = true.");

                    // Wrap loading in try-catch to handle CacheExpiredException
                    try
                    {
                        //LoadTilesFromList(da, manifestTilePaths, info, true, boundaryHash, attribution);
                        Message = "Valid Manifest.";
                        SetOutputs(da, info, new List<string>(), new List<Mesh>(), new List<object>(), attribution);
                        return;
                    }
                    catch (CacheExpiredException cex)
                    {
                        AddRuntimeMessage(GH_RuntimeMessageLevel.Error, cex.Message);
                        info.Add("ERROR: " + cex.Message);
                        SetOutputs(da, info, new List<string>(), new List<Mesh>(), new List<object>(), attribution);
                        return;
                    }
                }
                else
                {
                    info.Add("Manifest matches boundary; skipping download.");
                    LoadTilesFromList(da, manifestTilePaths, info, true, boundaryHash, attribution);
                    return;
                }
            }
            else if (!download)
            {
                info.Add("No valid manifest for this AOI (model+geodetic). Enable Download.");
                SetOutputs(da, info, new List<string>(), new List<Mesh>(), new List<object>(), string.Empty);
                Message = "No cached manifest";
                Grasshopper.Instances.RedrawCanvas();
                return;
            }

            try
            {
                // Download mode (or manifest invalid)
                Message = "Connecting to API...";
                Grasshopper.Instances.RedrawCanvas();

                var api = new GoogleTilesApi(apiKey, cacheFolder);
                var root = api.GetRootTileset();
                info.Add("Fetched root tileset.");

                try
                {
                    var wgs = GeoUtils.AoiToWgs(aoi);
                    info.Add(string.Format("AOI WGS84: [{0:F6},{1:F6}]–[{2:F6},{3:F6}]", wgs.minLon, wgs.minLat, wgs.maxLon, wgs.maxLat));
                    info.Add(string.Format("AOI Model: [{0:F2},{1:F2}]–[{2:F2},{3:F2}]", aoiBounds.Min.X, aoiBounds.Min.Y, aoiBounds.Max.X, aoiBounds.Max.Y));
                }
                catch (Exception exWgs2) { AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Failed AOI WGS84 bounds: " + exWgs2.Message); }

                Message = "Planning downloads...";
                Grasshopper.Instances.RedrawCanvas();

                TilesetWalker walker;
                try { walker = new TilesetWalker(api, aoi, maxLod, pois: pois, maxSSE: maxSse, k: k); } // Poi functionality
                catch (Exception exWalk)
                {
                    AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Failed to initialize TilesetWalker: " + exWalk.Message);
                    SetOutputs(da, info.Concat(new[] { "Error: Failed to initialize TilesetWalker." }).ToList(), usedFiles, new List<Mesh>(), new List<object>(), attribution);
                    return;
                }

                var plan = walker.PlanDownloads(root, true); // Poi functionality
                foreach (var line in walker.Stats.ToInfoLines()) info.Add(line);

                long capBytes = (long)(maxSizeGbOption * 1024 * 1024 * 1024);
                List<TileDownloadResult> tileResults = new List<TileDownloadResult>();
                long totalBytes = 0;
                int skippedForCap = 0;


                // PSEUDOCODE / PLAN (detailed):
                // 1. Replace the synchronous call to TileDownloader.Ensure(...) with a call that attempts to
                //    supply a progress callback so the component can update Message as downloads proceed.
                // 2. Use dynamic invocation to try calling an overload of Ensure that accepts a progress
                //    callback (so we don't have to modify TileDownloader here). The progress callback
                //    signature we expect: Action<int doneCount, int totalCount, long bytesDownloaded, string currentFile>
                // 3. In the progress callback update local fields downloadedTiles and downloadedBytes, then
                //    set Message with the formatted progress and call Grasshopper.Instances.RedrawCanvas().
                // 4. If the Ensure overload with a progress parameter is not available (runtime binder
                //    throws), fall back to the original Ensure(...) call that returns after completion.
                // 5. This keeps behavior backwards compatible while enabling progress updates when
                //    TileDownloader supports a progress callback overload.
                //
                // Implementation below replaces the single-line Ensure call with a try/catch dynamic invocation
                // that attempts to pass the progress callback and updates Message accordingly.

                if (plan.Count > 0)
                {
                    totalTiles = plan.Count; downloadedTiles = 0; downloadedBytes = 0; isDownloading = true;
                    Message = $"Downloading (0/{totalTiles})"; Grasshopper.Instances.RedrawCanvas();
                    var downloader = new TileDownloader(api, capBytes);

                    // Try to call an Ensure overload that accepts a progress callback.
                    // If such overload doesn't exist at runtime, fall back to the original call.
                    try
                    {
                        // Progress callback updates component fields and UI message.
                        Action<int, int, long, string> progress = (done, total, bytes, current) =>
                        {
                            try
                            {
                                downloadedTiles = done;
                                downloadedBytes = bytes;
                                var name = string.IsNullOrEmpty(current) ? "" : Path.GetFileName(current);
                                Message = $"Downloading {done}/{total}\r\n({bytes / (1024.0 * 1024.0):F1} MB)";
                                Grasshopper.Instances.RedrawCanvas();
                            }
                            catch
                            {
                                /* swallow UI update exceptions to avoid breaking downloads */
                            }
                        };

                        // Use dynamic to attempt calling Ensure with the progress callback.
                        // If TileDownloader has an overload like:
                        // List<TileDownloadResult> Ensure(List<...> plan, bool download, out long totalBytes, out int skipped, Action<int,int,long,string> progress)
                        // this invocation will succeed and provide live progress updates.
                        tileResults = ((dynamic)downloader).Ensure(plan, download, out totalBytes, out skippedForCap, progress);
                    }
                    catch (Microsoft.CSharp.RuntimeBinder.RuntimeBinderException)
                    {
                        // No matching overload found; fall back to existing behavior.
                        tileResults = downloader.Ensure(plan, download, out totalBytes, out skippedForCap);
                    }
                    catch (Exception)
                    {
                        // Any other exception should rethrow so outer try/catch handles it.
                        throw;
                    }

                    downloadedTiles = tileResults.Count; downloadedBytes = totalBytes;
                    double totalMB = totalBytes / (1024.0 * 1024.0);
                    Message = $"Downloaded {downloadedTiles}/{totalTiles} ({totalMB:F1} MB)"; Grasshopper.Instances.RedrawCanvas();
                    info.Add(string.Format("Tiles planned: {0}, downloaded/used: {1}, bytes: {2:n0}", plan.Count, tileResults.Count, totalBytes));
                    if (skippedForCap > 0) info.Add(string.Format("Skipped {0} tiles due to size cap ({1} GB).", skippedForCap, maxSizeGbOption));
                }
                else info.Add("No tiles planned (even after any relaxed attempt).");


                // Extract file paths for use
                var localGlbs = tileResults.Select(r => r.FilePath).ToList();
                usedFiles.AddRange(localGlbs);

                if (localGlbs.Count > 0) { Message = "Importing meshes..."; Grasshopper.Instances.RedrawCanvas(); }

                var meshes = new List<Mesh>();
                List<Grasshopper.Kernel.Types.GH_Material> mats = new List<Grasshopper.Kernel.Types.GH_Material>();
                HashSet<string> glbCopyrights = new HashSet<string>();

                if (localGlbs.Count > 0)
                {
                    var importMeshes = TileImporter.ImportMeshesOriented(localGlbs, out mats, out var importNotes, out glbCopyrights);
                    meshes = importMeshes ?? new List<Mesh>();
                    info.AddRange(importNotes);

                    // Use GLB copyrights as attribution if found
                    if (glbCopyrights.Count > 0)
                    {
                        attribution = string.Join("; ", glbCopyrights);
                        info.Add($"Attribution extracted from {glbCopyrights.Count} GLB file(s): " + attribution);
                        info.Add("IMPORTANT: Display the Google Maps logo with this attribution text.");
                        info.Add("See: https://developers.google.com/maps/documentation/tile/policies#logo");
                    }
                    else if (string.IsNullOrEmpty(attribution))
                    {
                        attribution = "© Google";
                        info.Add("No copyright found in GLB files; using default: " + attribution);
                    }
                }

                isDownloading = false;
                if (meshes.Count > 0)
                {
                    double totalMB = downloadedBytes / (1024.0 * 1024.0);
                    Message = $"Complete: {meshes.Count} meshes";
                    info.Add($"Complete: {meshes.Count} meshes ({totalMB:F1} MB)");
                }
                else { Message = "Complete: No meshes"; info.Add("Complete: No meshes imported."); }
                System.Threading.Thread.Sleep(100); Grasshopper.Instances.RedrawCanvas();

                if (tileResults.Count > 0)
                {
                    try
                    {
                        var manifest = new ManifestData
                        {
                            Version = 3,
                            BoundaryHash = boundaryHash,
                            LOD = maxLod,
                            MaxSSE = maxSse,
                            K = k,
                            Min = new double[] { aoiBounds.Min.X, aoiBounds.Min.Y, aoiBounds.Min.Z },
                            Max = new double[] { aoiBounds.Max.X, aoiBounds.Max.Y, aoiBounds.Max.Z },
                            MinLon = minLon,
                            MinLat = minLat,
                            MaxLon = maxLon,
                            MaxLat = maxLat,
                            WgsHash = wgsVertexHash,
                            Attribution = attribution, // Store attribution in manifest
                            GeneratedUtc = DateTime.UtcNow,
                            Tiles = tileResults.Select(r => new ManifestTile
                            {
                                File = Path.GetFileName(r.FilePath),
                                Bytes = r.Bytes,
                                CacheMetadata = r.CacheMetadata // Include cache metadata in manifest
                            }).ToList()
                        };
                        File.WriteAllText(manifestPath, JsonConvert.SerializeObject(manifest, Formatting.Indented));
                        info.Add("Wrote manifest: " + Path.GetFileName(manifestPath));
                    }
                    catch (Exception mex) { info.Add("Failed to write manifest: " + mex.Message); }
                }

                SetOutputs(da, info, usedFiles, meshes, mats.Cast<object>().ToList(), attribution);
            }
            catch (InvalidOperationException ex) when (ex.Message.Contains("EarthAnchor") || ex.Message.Contains("ActiveDoc"))
            {
                isDownloading = false; Message = "Error: " + ex.Message; Grasshopper.Instances.RedrawCanvas(); AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
                SetOutputs(da, info.Concat(new[] { "Error: " + ex.Message }).ToList(), new List<string>(), new List<Mesh>(), new List<object>(), attribution);
            }
            catch (Exception ex)
            {
                isDownloading = false; Message = "Error: " + ex.Message; Grasshopper.Instances.RedrawCanvas(); AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
                SetOutputs(da, info.Concat(new[] { ex.ToString() }).ToList(), new List<string>(), new List<Mesh>(), new List<object>(), attribution);
            }
        }

        private void LoadTilesFromList(IGH_DataAccess da, List<string> tilePaths, List<string> info, bool fromManifest, string boundaryHash, string attribution = "")
        {
            Message = fromManifest ? "Loading cached tiles..." : "Loading tiles..."; Grasshopper.Instances.RedrawCanvas();
            info.Add((fromManifest ? "Using manifest" : "Using cache") + " boundary hash: " + boundaryHash);
            info.Add("Tile files: " + tilePaths.Count);
            List<Grasshopper.Kernel.Types.GH_Material> mats;
            HashSet<string> glbCopyrights;
            var meshes = TileImporter.ImportMeshesOriented(tilePaths, out mats, out var importNotes, out glbCopyrights) ?? new List<Mesh>();
            info.AddRange(importNotes);

            // If attribution from manifest is empty and we have GLB copyrights, use those
            if (string.IsNullOrEmpty(attribution) && glbCopyrights.Count > 0)
            {
                attribution = string.Join("; ", glbCopyrights);
                info.Add($"Attribution extracted from {glbCopyrights.Count} GLB file(s)");
            }

            Message = $"Complete: {meshes.Count} meshes (cached)"; info.Add($"Loaded {meshes.Count} meshes from cache.");
            System.Threading.Thread.Sleep(60); Grasshopper.Instances.RedrawCanvas();
            SetOutputs(da, info, tilePaths, meshes, mats.Cast<object>().ToList(), attribution);
        }

        private void ValidateCachedTiles(GoogleTilesApi api, string manifestPath, List<string> info)
        {
            if (!File.Exists(manifestPath)) return;

            try
            {
                // Read manifest
                ManifestData manifestData;
                if (!TryLoadManifest(manifestPath, out manifestData) || manifestData.Tiles == null)
                {
                    info.Add("Cache validation skipped: manifest invalid or no tiles");
                    return;
                }

                int expiredCount = 0;
                int missingCount = 0;
                List<string> expiredTiles = new List<string>();

                foreach (var tile in manifestData.Tiles)
                {
                    if (string.IsNullOrEmpty(tile.File)) continue;

                    var tilePath = Path.Combine(Path.GetDirectoryName(manifestPath), tile.File);

                    if (!File.Exists(tilePath))
                    {
                        missingCount++;
                        continue;
                    }

                    // Check if tile has expired using cache metadata from manifest
                    if (GoogleTilesApi.IsTileExpired(tile.CacheMetadata))
                    {
                        expiredCount++;
                        expiredTiles.Add(tile.File);
                    }
                }

                if (expiredCount > 0)
                {
                    AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,
                        $"{expiredCount} cached tiles have EXPIRED based on HTTP Cache-Control headers. " +
                        $"Please enable 'Run' to re-download fresh tiles.");
                    info.Add($"WARNING: {expiredCount} tiles have expired:");
                    info.Add("  Expired tiles should be re-downloaded to ensure data freshness.");
                    info.Add("  Enable the 'Run' input to refresh expired content.");

                    // List first few expired tiles
                    int showCount = Math.Min(5, expiredTiles.Count);
                    for (int i = 0; i < showCount; i++)
                    {
                        info.Add($"  - {expiredTiles[i]}");
                    }
                    if (expiredTiles.Count > showCount)
                    {
                        info.Add($"  ... and {expiredTiles.Count - showCount} more");
                    }
                }

                if (missingCount > 0)
                {
                    AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,
                        $"{missingCount} tiles are missing from cache. " +
                        $"Enable 'Run' to re-download.");
                    info.Add($"WARNING: {missingCount} tiles missing from cache");
                }

                if (expiredCount == 0 && missingCount == 0)
                {
                    info.Add("Cache validation: All tiles are fresh and valid.");
                }
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark,
                    $"Could not validate cache: {ex.Message}");
                info.Add($"Cache validation skipped: {ex.Message}");
            }
        }

        private long SafeFileSize(string path) { try { return new FileInfo(path).Length; } catch { return 0; } }

        private string ComputeBoundaryHash(Curve c, int lod)
        {
            Polyline pl; if (!c.TryGetPolyline(out pl)) { pl = c.ToPolyline(0, 0, 0.1, 0.1).ToPolyline(); }
            if (pl == null || pl.Count == 0) return string.Empty;
            var sb = new StringBuilder();
            foreach (var pt in pl) { sb.Append(Math.Round(pt.X, 5)).Append(',').Append(Math.Round(pt.Y, 5)).Append(',').Append(Math.Round(pt.Z, 5)).Append(';'); }
            sb.Append("LOD=").Append(lod);
            using (var md5 = MD5.Create()) { var bytes = Encoding.UTF8.GetBytes(sb.ToString()); var hash = md5.ComputeHash(bytes); return string.Concat(hash.Select(b => b.ToString("x2"))); }
        }

        private string ComputeWgsVertexHash(Polyline pl)
        {
            if (pl == null || pl.Count == 0) return string.Empty;
            var sb = new StringBuilder();
            for (int i = 0; i < pl.Count; i++)
            {
                var w = Heron.Convert.XYZToWGS(pl[i]); // X=Lon, Y=Lat assumed
                sb.Append(Math.Round(w.X, 6)).Append(',').Append(Math.Round(w.Y, 6)).Append(';');
            }
            using (var md5 = MD5.Create()) { var bytes = Encoding.UTF8.GetBytes(sb.ToString()); var hash = md5.ComputeHash(bytes); return string.Concat(hash.Select(b => b.ToString("x2"))); }
        }

        private bool TryLoadManifest(string path, out ManifestData data)
        {
            data = null; if (!File.Exists(path)) return false; try { data = JsonConvert.DeserializeObject<ManifestData>(File.ReadAllText(path)); if (data == null) return false; if (data.Min == null || data.Max == null || data.Tiles == null) return false; return true; } catch { return false; }
        }

        // New validation including geodetic info. Falls back to legacy model-space only if Version < 2
        private bool NewBoundaryMatches(ManifestData data, BoundingBox modelCurrent, double modelTol, double minLon, double minLat, double maxLon, double maxLat, double degTol, string wgsHash, int lod)
        {
            if (data.Version >= 2)
            {
                if (data.LOD != lod) return false;
                bool wgsOk = Math.Abs(data.MinLon - minLon) <= degTol && Math.Abs(data.MinLat - minLat) <= degTol && Math.Abs(data.MaxLon - maxLon) <= degTol && Math.Abs(data.MaxLat - maxLat) <= degTol;
                bool hashOk = string.Equals(data.WgsHash, wgsHash, StringComparison.OrdinalIgnoreCase);
                if (!wgsOk || !hashOk) return false;
            }
            // Always verify model bbox (legacy compatibility)
            bool minOk = Math.Abs(data.Min[0] - modelCurrent.Min.X) <= modelTol && Math.Abs(data.Min[1] - modelCurrent.Min.Y) <= modelTol;
            bool maxOk = Math.Abs(data.Max[0] - modelCurrent.Max.X) <= modelTol && Math.Abs(data.Max[1] - modelCurrent.Max.Y) <= modelTol;
            return minOk && maxOk;
        }

        private void SetOutputs(IGH_DataAccess da, List<string> info, List<string> files, List<Mesh> meshes, List<object> mats, string attribution)
        {
            da.SetDataList(0, info);
            da.SetDataList(1, files);
            da.SetDataList(2, meshes);
            da.SetDataList(3, mats);
            da.SetData(4, attribution);

            // Create a simple Google Maps logo placeholder
            // TODO: Replace with actual Google Maps logo from resources once added
            // Download from: https://developers.google.com/maps/documentation/tile/policies#logo
            var logo = CreateGoogleMapsLogoPlaceholder();
            da.SetData(5, new Grasshopper.Kernel.Types.GH_ObjectWrapper(logo));
        }

        private System.Drawing.Bitmap CreateGoogleMapsLogoPlaceholder()
        {
            // Create a simple placeholder with "Google Maps Logo Required" text
            // Users should add the actual Google Maps logo per Google's requirements
            var bmp = new System.Drawing.Bitmap(200, 40);
            using (var g = System.Drawing.Graphics.FromImage(bmp))
            {
                g.Clear(System.Drawing.Color.White);
                using (var font = new System.Drawing.Font("Arial", 8, System.Drawing.FontStyle.Bold))
                using (var brush = new System.Drawing.SolidBrush(System.Drawing.Color.Black))
                {
                    var text = "Google Maps™";
                    var format = new System.Drawing.StringFormat
                    {
                        Alignment = System.Drawing.StringAlignment.Center,
                        LineAlignment = System.Drawing.StringAlignment.Center
                    };
                    g.DrawString(text, font, brush, new System.Drawing.RectangleF(0, 0, 200, 40), format);
                }

                // Draw a simple border
                using (var pen = new System.Drawing.Pen(System.Drawing.Color.LightGray, 1))
                {
                    g.DrawRectangle(pen, 0, 0, bmp.Width - 1, bmp.Height - 1);
                }
            }
            return bmp;
        }

        // Manifest classes
        private class ManifestData
        {
            public int Version { get; set; }
            public string BoundaryHash { get; set; }
            public int LOD { get; set; } // Added in version 2
            public int MaxSSE { get; set; } // Added in version 3
            public int K { get; set; } // Added in version 3
            public double[] Min { get; set; }
            public double[] Max { get; set; }
            public double MinLon { get; set; } // Added in version 2
            public double MinLat { get; set; }
            public double MaxLon { get; set; }
            public double MaxLat { get; set; }
            public string WgsHash { get; set; } // Added in version 2
            public string Attribution { get; set; } // Added for Google copyright
            public DateTime GeneratedUtc { get; set; }
            public List<ManifestTile> Tiles { get; set; }
        }
        private class ManifestTile
        {
            public string File { get; set; }
            public long Bytes { get; set; }
            public TileCacheMetadata CacheMetadata { get; set; } // Cache control metadata
        }
    }
}
