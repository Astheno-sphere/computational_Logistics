'use strict';

const { z } = require('zod');

function openApiToZod(schemaNode) {
  if (!schemaNode || typeof schemaNode !== 'object') return z.any();

  if (schemaNode.oneOf || schemaNode.anyOf) {
    const variants = (schemaNode.oneOf || schemaNode.anyOf).map(openApiToZod);
    return variants.length > 0 ? z.union(variants) : z.any();
  }

  let schema;
  const type = Array.isArray(schemaNode.type)
    ? schemaNode.type.find(t => t !== 'null')
    : schemaNode.type;

  switch (type) {
    case 'string':
      schema = z.string();
      break;
    case 'integer':
    case 'number':
      schema = z.number();
      break;
    case 'boolean':
      schema = z.boolean();
      break;
    case 'array':
      schema = z.array(openApiToZod(schemaNode.items || {}));
      break;
    case 'object':
      schema = objectToZod(schemaNode);
      break;
    default:
      schema = schemaNode.properties ? objectToZod(schemaNode) : z.any();
      break;
  }

  if (schemaNode.nullable || (Array.isArray(schemaNode.type) && schemaNode.type.includes('null'))) {
    schema = schema.nullable();
  }
  return schema;
}

function objectToZod(schemaNode) {
  const required = new Set(schemaNode.required || []);
  const shape = {};
  for (const [field, fieldSchema] of Object.entries(schemaNode.properties || {})) {
    let zodField = openApiToZod(fieldSchema);
    if (!required.has(field)) zodField = zodField.optional();
    shape[field] = zodField;
  }
  return z.object(shape).passthrough();
}

module.exports = { openApiToZod };
