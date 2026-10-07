# **Example 1: Performing Buffer and Intersection Operations on Shapefiles**

### **Objective**

In this example, we will perform spatial operations on two shapefiles:

- A **park polygon** (`Park.shp`).
- A **building polygon** (`Building.shp`).

We will:

1. Load the shapefiles.
2. **Buffer** the park polygon by **100 meters**.
3. Find the **intersection** between the buffered park and the building polygon.
4. Return the **geometry** of the intersection.

---

### **Steps**

#### **Step 1: Load Shapefiles**

- **Action**: Load two shapefiles: `Park.shp` and `Building.shp` from the specified location. The first shapefile contains the geometry of the park, and the second contains the building's geometry.
- **Prompt**: Please load the shapefiles located at `E:\Test\Example1\Park.shp` and `E:\Test\Example1\Building.shp` using `gis-mcp`.

#### **Step 2: Buffer Operation**

- **Action**: Perform a **buffer operation** on the park geometry, expanding it by **100 meters**. This will create a zone around the park.
- **Prompt**: Perform a **buffer operation** with a distance of **100 meters** on the geometry of the park (from `Park.shp`).

#### **Step 3: Intersection**

- **Action**: Find the **intersection** between the buffered park geometry and the building geometry. This will give us the overlapping area between the park and the building.
- **Prompt**: Find the **intersection** between the buffered geometry of the park and the geometry of the building (from `Building.shp`).

#### **Step 4: Return the Intersection Geometry**

- **Action**: Return the **intersection geometry** in **WKT format**. This will represent the region where the buffered park intersects with the building.
- **Prompt**: Return the **geometry** of the intersection as WKT format.

---

### **Expected Output**

- **Buffer Geometry**: The geometry of the park will be expanded by 100 meters, creating a **buffer zone** around it.
- **Intersection Geometry**: The area where the **buffered park** overlaps with the **building** will be returned as a **WKT geometry**.

---

### **Use Case**

In environmental management and land-use planning, buffer zones are critical for protecting sensitive natural areas, such as rivers.
For example, many countries or regions have legal restrictions on land use within certain distances of rivers to prevent pollution, protect biodiversity, and ensure sustainable land development.
By performing a **buffer operation** around a river's geometry and checking the **intersection** with nearby development projects, planners can easily identify if any buildings, roads, or other infrastructures are within the protected zone. This ensures that the development does not negatively impact the environment and adheres to local regulations for water protection.

### 📺 Video Tutorial

For a deeper understanding of how these operations work in practice, check out this YouTube video:

<iframe width="560" height="315" src="https://www.youtube.com/embed/nC5H6uDtABs" frameborder="0" allowfullscreen></iframe>
