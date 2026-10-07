#include "bindings.h"

#if defined(RHINOCORE_BINDINGS)

BND_RhinoDoc ActiveRhinoDoc()
{
  BND_RhinoDoc rc;
  rc.m_doc_serial_number = CRhinoDoc::RuntimeSerialNumber(RhinoApp().ActiveDoc());
  return rc;
}

BND_UUID BND_RhinoDocObjectTable::AddPoint1(double x, double y, double z)
{
  return AddPoint2(ON_3dPoint(x, y, z));
}

BND_UUID BND_RhinoDocObjectTable::AddPoint2(const ON_3dPoint& point)
{
  CRhinoDoc* doc = CRhinoDoc::FromRuntimeSerialNumber(m_doc_serial_number);
  if (doc)
  {
    CRhinoPointObject* obj = doc->AddPointObject(point);
    if (obj)
      return ON_UUID_to_Binding(obj->Id());
  }
  return ON_UUID_to_Binding(ON_nil_uuid);
}

BND_UUID BND_RhinoDocObjectTable::AddLine1(const ON_3dPoint& from, const ON_3dPoint& to)
{
  ON_Line line(from, to);
  return AddLine2(line);
}
BND_UUID BND_RhinoDocObjectTable::AddLine2(const ON_Line& line)
{
  CRhinoDoc* doc = CRhinoDoc::FromRuntimeSerialNumber(m_doc_serial_number);
  if (doc)
  {
    CRhinoCurveObject* obj = doc->AddCurveObject(line);
    if (obj)
      return ON_UUID_to_Binding(obj->Id());
  }
  return ON_UUID_to_Binding(ON_nil_uuid);
}

void initRhinoDocBindings(rh3dmpymodule& m)
{
  py::class_<BND_RhinoDoc>(m, "RhinoDoc")
    .def_static("ActiveDoc", &ActiveRhinoDoc)
    .def_prop_ro("Objects", &BND_RhinoDoc::ObjectTable)
    ;

  py::class_<BND_RhinoDocObjectTable>(m, "ObjectTable")
    .def("AddPoint", &BND_RhinoDocObjectTable::AddPoint1, py::arg("x"), py::arg("y"), py::arg("z"))
    .def("AddPoint", &BND_RhinoDocObjectTable::AddPoint2, py::arg("point"))
    .def("AddLine", &BND_RhinoDocObjectTable::AddLine1, py::arg("from"), py::arg("to"))
    .def("AddLine", &BND_RhinoDocObjectTable::AddLine2, py::arg("line"))
    ;
}
#endif
