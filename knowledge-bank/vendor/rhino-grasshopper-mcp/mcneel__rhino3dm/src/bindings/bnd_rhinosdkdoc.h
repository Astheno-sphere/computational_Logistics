#include "bindings.h"

#pragma once

#if defined(RHINOCORE_BINDINGS)

void initRhinoDocBindings(rh3dmpymodule& m);

class BND_RhinoDocObjectTable
{
  unsigned int m_doc_serial_number = 0;
public:
  BND_RhinoDocObjectTable(unsigned int docSN) : m_doc_serial_number(docSN) {}

  BND_UUID AddPoint1(double x, double y, double z);
  BND_UUID AddPoint2(const ON_3dPoint& point);
  BND_UUID AddLine1(const ON_3dPoint& from, const ON_3dPoint& to);
  BND_UUID AddLine2(const ON_Line& line);
};

class BND_RhinoDoc
{
public:
  unsigned int m_doc_serial_number = 0;

  BND_RhinoDocObjectTable ObjectTable() { return BND_RhinoDocObjectTable(m_doc_serial_number); }
};

#endif

