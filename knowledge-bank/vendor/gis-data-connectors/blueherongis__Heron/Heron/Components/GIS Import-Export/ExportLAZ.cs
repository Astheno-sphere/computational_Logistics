using Eto.Drawing;
using Eto.Forms;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Types;
using LASzip.Net;
using Rhino.Geometry;
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Windows.Forms;

namespace Heron.Components.GIS_Import_Export
{
    public class ExportLAZ : HeronComponent
    {
        /// <summary>
        /// Initializes a new instance of the ExportLAZ class.
        /// </summary>
        public ExportLAZ()
          : base("Export LAZ", "ExportLAZ",
              "Export LAZ files",
              "GIS Import | Export")
        {
        }

        /// <summary>
        /// Sets the exposure level of the component.
        /// </summary>
        public override Grasshopper.Kernel.GH_Exposure Exposure
        {
            get { return GH_Exposure.secondary; }
        }

        /// <summary>
        /// Registers all the input parameters for this component.
        /// </summary>
        protected override void RegisterInputParams(GH_Component.GH_InputParamManager pManager)
        {
            pManager.AddTextParameter("File Path", "FP", "File path to save the LAZ file", GH_ParamAccess.item);
            // There is no AddPointCloudParameter method. Use AddGenericParameter for PointCloud input.
            pManager.AddGenericParameter("PointCloud", "PC", "Point Cloud to export as LAZ", GH_ParamAccess.item);
            pManager.AddTextParameter("Point Cloud SRS", "SRS", "Spatial reference in Well Known Text (WKT) format.  " +
                "This can also be a well-known SRS such as 'WGS84' " +
                "or an EPSG code such as 'EPSG:4326'.  " +
                "No transformations will be made, " +
                "this only sets the WKT VLR in the header of the LAZ file.  " +
                "Points should already be in the SRS.  Use the CoordinateTransformation component if needed.", GH_ParamAccess.item, "");
            pManager.AddBooleanParameter("Run", "R", "Set to true to run the export", GH_ParamAccess.item, false);
        }

        /// <summary>
        /// Registers all the output parameters for this component.
        /// </summary>
        protected override void RegisterOutputParams(GH_Component.GH_OutputParamManager pManager)
        {
            pManager.AddTextParameter("File Path", "FP", "Path to the exported LAZ file", GH_ParamAccess.item);
        }

        /// <summary>
        /// This is the method that actually does the work.
        /// </summary>
        /// <param name="DA">The DA object is used to retrieve from inputs and store in outputs.</param>
        protected override void SolveInstance(IGH_DataAccess DA)
        {
            // Input variables
            string filePath = string.Empty;
            string pcSRS = string.Empty;
            Rhino.Geometry.PointCloud pcWrapper = null;
            bool run = false;
            if (!DA.GetData(0, ref filePath)) return;
            if (!DA.GetData(1, ref pcWrapper)) return;
            if (!DA.GetData(2, ref pcSRS)) return;
            if (!DA.GetData(3, ref run)) return;
            if (!run) return;

            var pointCloud = pcWrapper;
            if (pointCloud == null)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Invalid PointCloud input.");
                return;
            }
            if (Path.GetExtension(filePath).ToLower() != ".laz")
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "File extension must be .laz");
                return;
            }
            if (!Directory.Exists(Path.GetDirectoryName(filePath)))
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Folder does not exist or is an invalid folder location.");
                return;
            }
            var pcSrsWkt = string.Empty;
            if (!string.IsNullOrEmpty(pcSRS))
            {
                ///GDAL setup
                Heron.GdalConfiguration.ConfigureOgr();
                // Validate SRS string if necessary
                if (string.Equals(pcSRS, "HeronSRS", StringComparison.OrdinalIgnoreCase)) pcSRS = HeronSRS.Instance.SRS;
                OSGeo.OSR.SpatialReference sourceSRS = new OSGeo.OSR.SpatialReference("");
                sourceSRS.SetFromUserInput(pcSRS);
                if (sourceSRS.Validate() == 1)
                {
                    AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Invalid Source SRS.");
                    return;
                }
                sourceSRS.ExportToWkt(out pcSrsWkt, null);
            }


            try
            {
                var lazWriter = new laszip();
                try
                {
                    // Set up the header information
                    var header = new laszip_header();

                    // Create headers and set necessary properties
                    header.file_source_ID = (ushort) 0;
                    header.version_major = (byte)1;
                    header.version_minor = (byte)4;

                    header.header_size = (ushort)375;  // Mandatory for LAS 1.4
                    header.point_data_format = (byte) 7; // Format 7 = Base Point + RGB (LAS 1.4). Use 8 for NIR as well.
                    header.point_data_record_length = (ushort) 36; // Required length for Format 7
                    
                    header.global_encoding = 17; // 17 = 16 (WKT) + 1 (Adjusted GPS Time)
                    // Add SRS to the header as a VLR
                    if (!string.IsNullOrEmpty(pcSrsWkt))
                    {
                        // Add WKT VLR
                        var wktVlr = new laszip_vlr();

                        // Convert the string to bytes
                        byte[] sourceBytes = System.Text.Encoding.ASCII.GetBytes("LASF_Projection");
                        // Copy character by character into the pre-existing fixed-size array. user_id is 16 bytes.
                        for (int i = 0; i < 16; i++)
                        {
                            if (i < sourceBytes.Length)
                                wktVlr.user_id[i] = sourceBytes[i];
                            else
                                wktVlr.user_id[i] = 0; // Ensure null padding
                        }
                        
                        wktVlr.record_id = 2112; // Record ID for WKT
                        
                        byte[] descBytes = System.Text.Encoding.ASCII.GetBytes("OGC WKT Spatial Reference");
                        // Copy character by character into the pre-existing fixed-size array. description is 32 bytes.
                        for (int i = 0; i < 32; i++)
                        {
                            if (i < descBytes.Length)
                                wktVlr.description[i] = descBytes[i];
                            else
                                wktVlr.description[i] = 0; // Padding with null bytes
                        }
                        var wktBytes = Encoding.ASCII.GetBytes(pcSrsWkt);

                        wktVlr.record_length_after_header = (ushort) wktBytes.Length;
                        wktVlr.data = wktBytes;
                        header.vlrs.Add(wktVlr);
                    }

                    header.number_of_point_records = (uint) 0; // For LAS 1.4 Point Formats 6-10, legacy fields should be 0
                    header.number_of_points_by_return[0] = (uint) 0;

                    header.extended_number_of_point_records = (ulong) pointCloud.Count; // Use extended field for actual count
                    header.extended_number_of_points_by_return[0] = (ulong) pointCloud.Count; // All points are 1st returns


                    /// Transform point cloud given EAP and HeronSRS if available
                    /// This may not be necessary. Will depend on user needs.
                    /// Set up GDAL/OGR
                    //Heron.GdalConfiguration.ConfigureGdal();
                    /// Set transform from input spatial reference to Heron spatial reference
                    //var heronSrs = new OSGeo.OSR.SpatialReference("");
                    //heronSrs.SetFromUserInput(HeronSRS.Instance.SRS);
                    /// Apply EAP to HeronSRS
                    //var modelToHeronSrsTransform = Heron.Convert.GetModelToUserSRSTransform(heronSrs);
                    /// Transform point cloud as a whole or do this per-point during writing
                    //pointCloud.Transform(modelToHeronSrsTransform);

                    // Set min/max bounds 
                    var bbox = pointCloud.GetBoundingBox(true);
                    header.min_x = bbox.Min.X;
                    header.min_y = bbox.Min.Y;
                    header.min_z = bbox.Min.Z;
                    header.max_x = bbox.Max.X;
                    header.max_y = bbox.Max.Y;
                    header.max_z = bbox.Max.Z;

                    // Set scale and offset (crucial for precision and file size)
                    // Scale: This determines the precision of your data. If your units are meters,
                    // a scale of 0.01 provides centimeter accuracy. Common values are 0.01, 0.001 (millimeter),
                    // or 0.0001 depending on your source data's resolution.
                    // Offset: This is typically set to the minimum coordinate values to keep integer representations small.
                    header.x_scale_factor = 0.01;
                    header.y_scale_factor = 0.01;
                    header.z_scale_factor = 0.01;
                    header.x_offset = bbox.Min.X;
                    header.y_offset = bbox.Min.Y;
                    header.z_offset = bbox.Min.Z;

                    // Set creation day and year
                    header.file_creation_day = (ushort) System.DateTime.Now.DayOfYear;
                    header.file_creation_year = (ushort)System.DateTime.Now.Year;


                    header.number_of_variable_length_records = (uint)header.vlrs.Count;
                    //header.number_of_extended_variable_length_records = (uint)header.;

                    // If you have no VLRs:
                    header.offset_to_point_data = 375;

                    // If you HAVE VLRs, calculate the total:
                    uint vlrTotalSize = 0;
                    foreach (var vlr in header.vlrs)
                    {
                        vlrTotalSize += (uint)(54 + vlr.record_length_after_header);
                    }
                    header.offset_to_point_data = 375 + vlrTotalSize;

                    // Set the header to the writer
                    lazWriter.set_header(header);

                    // Open the file for writing
                    lazWriter.open_writer(filePath, true);


                    // Write points
                    foreach (var pt in pointCloud)
                    {
                        // Convert the points to the library's internal representation
                        // set_coordinates automatically applies scale and offset to double coordinate values to get integers
                        double[] coords = new double[] { pt.X, pt.Y, pt.Z };
                        lazWriter.set_coordinates(coords);

                        // Color: stored in an array [Red, Green, Blue, NIR]
                        // Values must be 16-bit (0 - 65535)
                        lazWriter.point.rgb[0] = (ushort)(pt.Color.R * 256); // Red
                        lazWriter.point.rgb[1] = (ushort)(pt.Color.G * 256); // Green
                        lazWriter.point.rgb[2] = (ushort)(pt.Color.B * 256); // Blue
                        //lazWriter.point.rgb[3] = 0; // NIR (Near-Infrared not used here, use point format 8)

                        // Set other point attributes if necessary (intensity, classification, etc.)
                        //lazWriter.point.intensity = (ushort) pt.PointValue; // PointValue used as intensity, but may not be appropriate
                        lazWriter.point.classification = 0;
                        lazWriter.point.extended_classification = 0;
                        lazWriter.point.return_number = 0;
                        lazWriter.point.extended_return_number = 0;

                        // Write the point to the file
                        lazWriter.write_point();
                    }
                }
                finally
                {
                    // Clean up
                    try
                    {
                        lazWriter.clean();
                        lazWriter.close_writer();
                    }
                    catch
                    {
                    }
                }

                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "LAZ file exported successfully.");
                DA.SetData(0, filePath);
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, $"Error during export: {ex.Message}");
                return;
            }
        }

        /// <summary>
        /// Provides an Icon for the component.
        /// </summary>
        protected override System.Drawing.Bitmap Icon
        {
            get
            {
                //You can add image files to your project resources and access them like this:
                // return Resources.IconForThisComponent;
                return Properties.Resources.shp;
            }
        }

        /// <summary>
        /// Gets the unique ID for this component. Do not change this ID after release.
        /// </summary>
        public override Guid ComponentGuid
        {
            get { return new Guid("3652D57E-547B-4370-989D-50BD328CAC8F"); }
        }
    }
}