# **Example 2: CRS Check, Reprojection, Area & Distance Calculations on a Parcel Shapefile**

### **Objective**

In this example, we will perform spatial QA and measurements on a single shapefile:

We will:

1. Load the shapefile and check its CRS.
2. Transform the coordinates to geographic coordinates.
3. For each polygon, calculate the area (in square meters) of features that meet a specific condition.
4. Calculate the distance (in meters) between the centroids of the parcels.

---

### **Steps**

#### **Step 1: Load Shapefile & Check CRS**

- **Action**: Load the shapefile `Parcel.shp` and report its current Coordinate Reference System (CRS).
- **Prompt**: Please load the shapefile located at `E:\Test\Example2\Parcel.shp` and check/report its CRS using `gis-mcp`.

#### **Step 2: Transform Coordinates to Geographic**

- **Action**: Reproject the shapefile to geographic coordinates (latitude/longitude).
- **Prompt**: Please transform the coordinates of `E:\Test\Example2\Parcel.shp` to geographic coordinates (e.g., WGS 84 / EPSG:4326) using `gis-mcp`, and save/use the transformed layer for subsequent steps.

#### **Step 3: Area Calculations by Landuse**

- **Action**: For each polygon in the shapefile, compute the **area in square meters** for parcels with:
  - **Landuse = 1** (residential)
  - **Landuse = 2** (commercial)
- **Prompt**: Using the transformed parcel layer, **calculate the area (m²)** of polygons where **Landuse = 1** and where **Landuse = 2**, and **return the areas in square meters** (per polygon and/or totals).

#### **Step 4: Distance Between Parcel Centroids**

- **Action**: Identify the parcel(s) with **Landuse = 1** and **Landuse = 2**, compute their **centroids**, and measure the **distance in meters** between these centroids.
- **Prompt**: Please **calculate the distance (meters)** between the centroids of the two parcels with **Landuse = 1** and **Landuse = 2** using the transformed layer, and **return the distance**.

---

### **Use Case**

In urban planning and cadastral management, confirming the **CRS** and ensuring correct **reprojection** are essential before any measurement. Calculating **parcel areas** by land-use class supports taxation, zoning compliance, and infrastructure planning. Measuring **distances between parcel centroids** helps assess proximity—for example, understanding how close residential parcels are to commercial areas for mixed-use planning, access to services, or impact studies.

### 📺 Video Tutorial

For a deeper understanding of how these operations work in practice, check out this YouTube video:

<iframe width="560" height="315" src="https://www.youtube.com/embed/0EqHwoT_TFo" frameborder="0" allowfullscreen></iframe>
