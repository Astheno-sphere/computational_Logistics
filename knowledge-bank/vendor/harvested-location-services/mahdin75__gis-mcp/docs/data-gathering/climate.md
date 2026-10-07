### Climate Data (ERA5 via `cdsapi`)

The **Climate Data** tool in GIS-MCP allows you to download climate variables (e.g., temperature, precipitation, wind, humidity) from the [Copernicus Climate Data Store (CDS)](https://cds.climate.copernicus.eu/).

---

#### Installation

To enable climate data downloads, install GIS-MCP with the **climate** extra:

```bash
pip install gis-mcp[climate]
```

#### Authentication (Required)

Before using the tool, follow these steps:

---

##### 1. Create a CDS Account
- Create a free account at the [CDS Portal](https://cds.climate.copernicus.eu/).

---

##### 2. Get Your API Key
- Go to your [CDS Profile](https://cds.climate.copernicus.eu/user)  
- Copy your **API key**.

---

##### 3. Create the `.cdsapirc` File
Create a file named `.cdsapirc` in your **home directory**:

- **Windows:**  
  `C:\Users\<username>\.cdsapirc`

- **Linux/Mac:**  
  `/home/<username>/.cdsapirc`

Add the following content (replace with your real key):

```yaml
url: https://cds.climate.copernicus.eu/api
key: <UID>:<API_KEY>
```

---

##### 4. Accept License Agreements

- Go to the [ERA5 Single Levels dataset page](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels)  
- Scroll down to **Terms of use**  
- Click **Accept**



#### Parameters

- **variable** (`str`, required)  
  The climate variable you want to download.  
  Examples: `"2m_temperature"`, `"total_precipitation"`, `"surface_pressure"`.  

- **year** (`str`, required)  
  The year of interest, e.g., `"2021"`.  

- **month** (`str`, required)  
  The month as two digits, `"01"` through `"12"`.  

- **day** (`str`, required)  
  The day as two digits, `"01"` through `"31"`.  

- **time** (`str`, optional, default = `"12:00"`)  
  The time of day in hours and minutes (UTC).  

- **dataset** (`str`, optional, default = `"reanalysis-era5-single-levels"`)  
  The CDS dataset name.  

- **format** (`str`, optional, default = `"netcdf"`)  
  The file format. Supported values: `"netcdf"`, `"grib"`.  

- **path** (`str`, optional)  
  Custom output folder. If not provided, data is saved under `data/climate_data/`.


#### Example Usage

**Prompt:**
```bash
Using gis-mcp Download 2m temperature for 2021-01-01 at 12:00 UTC.
```