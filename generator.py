#!/usr/bin/env python3
"""
Enhanced curl command generator with comprehensive API documentation.
Creates detailed curl files with full context for each endpoint.
FIXED: Properly handles different content types including multipart/form-data
"""

import yaml
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


def parse_text_diff(file_path: str) -> Dict[str, List[Dict[str, str]]]:
    """Parse the text format API diff file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        result = {
            'added': [],
            'deleted': [],
            'modified': []
        }
        
        current_section = None
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and separators
            if not line or line.startswith('---'):
                continue
            
            # Detect sections
            if line.startswith('### New Endpoints:'):
                current_section = 'added'
                continue
            elif line.startswith('### Deleted Endpoints:'):
                current_section = 'deleted'
                continue
            elif line.startswith('### Modified Endpoints:'):
                current_section = 'modified'
                continue
            
            # Parse endpoint lines
            if current_section and line and not line.startswith('-'):
                # Parse "METHOD /path/" format
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    method = parts[0].strip()
                    path = parts[1].strip()
                    
                    endpoint = {
                        'method': method,
                        'path': path
                    }
                    
                    if current_section == 'modified':
                        endpoint['modifications'] = []
                    
                    result[current_section].append(endpoint)
            
            # Parse modification details
            elif current_section == 'modified' and line.startswith('-'):
                if result[current_section]:
                    # Add modification details to the last endpoint
                    result[current_section][-1]['modifications'].append(line)
        
        return result
    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return {'added': [], 'deleted': [], 'modified': []}
    except Exception as e:
        print(f"Error parsing text diff file '{file_path}': {e}")
        return {'added': [], 'deleted': [], 'modified': []}


def load_openapi_spec(file_path: str) -> Dict[Any, Any]:
    """Load and parse OpenAPI YAML specification."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: OpenAPI file '{file_path}' not found.")
        return {}
    except yaml.YAMLError as e:
        print(f"Error parsing OpenAPI YAML file '{file_path}': {e}")
        return {}


def resolve_schema_ref(openapi_spec: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve $ref references in OpenAPI schema."""
    if not isinstance(schema, dict):
        return schema
    
    if '$ref' in schema:
        ref_path = schema['$ref']
        if ref_path.startswith('#/'):
            # Remove the '#/' prefix and split the path
            path_parts = ref_path[2:].split('/')
            
            # Navigate through the OpenAPI spec to find the referenced schema
            current = openapi_spec
            try:
                for part in path_parts:
                    current = current[part]
                return current
            except (KeyError, TypeError):
                print(f"Warning: Could not resolve reference {ref_path}")
                return schema
    
    return schema


def get_parameter_info(openapi_spec: Dict[str, Any], path: str, method: str) -> Dict[str, List[Dict]]:
    """Extract comprehensive parameter information."""
    try:
        path_item = openapi_spec.get('paths', {}).get(path, {})
        operation = path_item.get(method.lower(), {})
        parameters = operation.get('parameters', []) + path_item.get('parameters', [])
        
        param_info = {
            'path': [],
            'query': [],
            'header': [],
            'cookie': []
        }
        
        for param in parameters:
            param_type = param.get('in', 'query')
            if param_type in param_info:
                param_details = {
                    'name': param.get('name', 'unknown'),
                    'required': param.get('required', False),
                    'description': param.get('description', 'No description available'),
                    'schema': param.get('schema', {}),
                    'example': get_realistic_example_value(param.get('schema', {}), param.get('name', ''), openapi_spec)
                }
                param_info[param_type].append(param_details)
        
        return param_info
    except Exception as e:
        print(f"Warning: Could not extract parameter info for {method} {path}: {e}")
        return {'path': [], 'query': [], 'header': [], 'cookie': []}


def get_request_body_info(openapi_spec: Dict[str, Any], path: str, method: str) -> Optional[Dict]:
    """Get detailed request body information."""
    try:
        path_item = openapi_spec.get('paths', {}).get(path, {})
        operation = path_item.get(method.lower(), {})
        request_body = operation.get('requestBody', {})
        
        if not request_body:
            return None
        
        content = request_body.get('content', {})
        description = request_body.get('description', 'No description available')
        required = request_body.get('required', False)
        
        body_info = {
            'description': description,
            'required': required,
            'content_types': {}
        }
        
        for content_type, content_data in content.items():
            schema = content_data.get('schema', {})
            example_data = get_realistic_example_value(schema, 'request_body', openapi_spec)
            
            body_info['content_types'][content_type] = {
                'schema': schema,
                'example': example_data
            }
        
        return body_info
    except Exception as e:
        print(f"Warning: Could not get request body info for {method} {path}: {e}")
        return None


def get_response_info(openapi_spec: Dict[str, Any], path: str, method: str) -> Dict[str, Dict]:
    """Get detailed response information for all status codes."""
    try:
        path_item = openapi_spec.get('paths', {}).get(path, {})
        operation = path_item.get(method.lower(), {})
        responses = operation.get('responses', {})
        
        response_info = {}
        
        for status_code, response_data in responses.items():
            description = response_data.get('description', 'No description available')
            content = response_data.get('content', {})
            headers = response_data.get('headers', {})
            
            response_info[status_code] = {
                'description': description,
                'headers': headers,
                'content': {}
            }
            
            for content_type, content_data in content.items():
                schema = content_data.get('schema', {})
                example_data = get_realistic_example_value(schema, 'response', openapi_spec)
                
                response_info[status_code]['content'][content_type] = {
                    'schema': schema,
                    'example': example_data
                }
        
        return response_info
    except Exception as e:
        print(f"Warning: Could not get response info for {method} {path}: {e}")
        return {}


def get_realistic_example_value(schema: Dict[str, Any], field_name: str = "", openapi_spec: Dict[str, Any] = None) -> Any:
    """Generate realistic example values based on OpenAPI schema and field names."""
    if not isinstance(schema, dict):
        return None
    
    # Resolve schema references
    if openapi_spec:
        if '$ref' in schema:
            schema = resolve_schema_ref(openapi_spec, schema)
        elif 'allOf' in schema:
            merged_schema = {}
            for sub_schema in schema['allOf']:
                resolved = resolve_schema_ref(openapi_spec, sub_schema) if '$ref' in sub_schema else sub_schema
                merged_schema.update(resolved)
            schema = merged_schema
    
    # Check for explicit example
    if 'example' in schema:
        return schema['example']
    
    # Check for enum values
    if 'enum' in schema and schema['enum']:
        return schema['enum'][0]
    
    # Generate based on type and field name
    schema_type = schema.get('type', 'string')
    field_lower = field_name.lower()
    
    if schema_type == 'string':
        # Format-based examples
        if schema.get('format') == 'email':
            return "john.doe@example.com"
        elif schema.get('format') == 'date':
            return "2024-01-15"
        elif schema.get('format') == 'date-time':
            return "2024-01-15T10:30:00Z"
        elif schema.get('format') == 'uuid':
            return "550e8400-e29b-41d4-a716-446655440000"
        elif schema.get('format') == 'uri' or 'url' in field_lower:
            return "https://example.com/resource"
        elif schema.get('format') == 'binary':
            return "@/path/to/file"
        
        # Field name-based examples
        if 'email' in field_lower:
            return "john.doe@example.com"
        elif 'name' in field_lower:
            if 'first' in field_lower:
                return "John"
            elif 'last' in field_lower:
                return "Doe"
            elif 'file' in field_lower:
                return "@/path/to/video.mp4"
            else:
                return "Daily Diary Entry"
        elif 'title' in field_lower:
            return "Today's Activities"
        elif 'description' in field_lower:
            return "Students worked on math problems and participated in group discussions"
        elif 'phone' in field_lower:
            return "+1-234-567-8900"
        elif 'address' in field_lower:
            return "123 Main St, City, State 12345"
        elif 'id' in field_lower or field_lower.endswith('_id'):
            return "123"
        elif 'status' in field_lower:
            return "active"
        elif 'type' in field_lower:
            return "standard"
        elif 'date' in field_lower:
            return "2024-01-15"
        elif 'time' in field_lower:
            return "10:30:00"
        elif 'file' in field_lower or 'video' in field_lower or 'image' in field_lower:
            return "@/path/to/file"
        
        return "sample_string_value"
        
    elif schema_type == 'integer':
        if 'id' in field_lower:
            return 123
        elif 'count' in field_lower or 'total' in field_lower:
            return 25
        elif 'score' in field_lower:
            return 85
        elif 'age' in field_lower:
            return 28
        return 42
        
    elif schema_type == 'number':
        if 'price' in field_lower or 'cost' in field_lower:
            return 29.99
        elif 'rate' in field_lower:
            return 4.5
        elif 'percentage' in field_lower:
            return 75.5
        return 3.14
        
    elif schema_type == 'boolean':
        if 'active' in field_lower or 'enabled' in field_lower:
            return True
        elif 'deleted' in field_lower or 'disabled' in field_lower:
            return False
        return True
        
    elif schema_type == 'array':
        item_schema = schema.get('items', {})
        example_item = get_realistic_example_value(item_schema, field_name + "_item", openapi_spec)
        return [example_item] if example_item is not None else []
        
    elif schema_type == 'object':
        obj = {}
        properties = schema.get('properties', {})
        for prop_name, prop_schema in properties.items():
            obj[prop_name] = get_realistic_example_value(prop_schema, prop_name, openapi_spec)
        return obj
    
    return None


def get_schema_structure(schema: Dict[str, Any], indent: int = 0, openapi_spec: Dict[str, Any] = None) -> List[str]:
    """Generate detailed schema structure with field types and names."""
    lines = []
    indent_str = "  " * indent
    
    if not isinstance(schema, dict):
        return [f"{indent_str}unknown_type"]
    
    # Resolve schema references
    if openapi_spec:
        schema = resolve_schema_ref(openapi_spec, schema)
    
    schema_type = schema.get('type', 'unknown')
    
    if schema_type == 'object':
        properties = schema.get('properties', {})
        required_fields = set(schema.get('required', []))
        
        if not properties:
            lines.append(f"{indent_str}object (no properties defined)")
            return lines
        
        for field_name, field_schema in properties.items():
            required_marker = " (required)" if field_name in required_fields else " (optional)"
            field_type = field_schema.get('type', 'unknown')
            
            # Handle different field types
            if field_type == 'object':
                lines.append(f"{indent_str}{field_name}: object{required_marker}")
                lines.extend(get_schema_structure(field_schema, indent + 1, openapi_spec))
            elif field_type == 'array':
                items_schema = field_schema.get('items', {})
                items_type = items_schema.get('type', 'unknown')
                if items_type == 'object':
                    lines.append(f"{indent_str}{field_name}: array of objects{required_marker}")
                    lines.extend(get_schema_structure(items_schema, indent + 1, openapi_spec))
                else:
                    lines.append(f"{indent_str}{field_name}: array of {items_type}{required_marker}")
            else:
                # Add format information if available
                format_info = field_schema.get('format', '')
                format_str = f" (format: {format_info})" if format_info else ""
                
                # Add enum information if available
                enum_values = field_schema.get('enum', [])
                enum_str = f" (enum: {', '.join(map(str, enum_values))})" if enum_values else ""
                
                lines.append(f"{indent_str}{field_name}: {field_type}{format_str}{enum_str}{required_marker}")
    
    elif schema_type == 'array':
        items_schema = schema.get('items', {})
        items_type = items_schema.get('type', 'unknown')
        if items_type == 'object':
            lines.append(f"{indent_str}array of objects:")
            lines.extend(get_schema_structure(items_schema, indent + 1, openapi_spec))
        else:
            lines.append(f"{indent_str}array of {items_type}")
    
    else:
        format_info = schema.get('format', '')
        format_str = f" (format: {format_info})" if format_info else ""
        enum_values = schema.get('enum', [])
        enum_str = f" (enum: {', '.join(map(str, enum_values))})" if enum_values else ""
        lines.append(f"{indent_str}{schema_type}{format_str}{enum_str}")
    
    return lines


def get_operation_info(openapi_spec: Dict[str, Any], path: str, method: str) -> Dict:
    """Get operation-level information like summary, description, tags."""
    try:
        path_item = openapi_spec.get('paths', {}).get(path, {})
        operation = path_item.get(method.lower(), {})
        
        return {
            'summary': operation.get('summary', 'No summary available'),
            'description': operation.get('description', 'No description available'),
            'tags': operation.get('tags', []),
            'operationId': operation.get('operationId', ''),
            'deprecated': operation.get('deprecated', False)
        }
    except Exception as e:
        print(f"Warning: Could not get operation info for {method} {path}: {e}")
        return {
            'summary': 'No summary available',
            'description': 'No description available',
            'tags': [],
            'operationId': '',
            'deprecated': False
        }


def resolve_path_with_examples(path: str, param_info: Dict) -> Tuple[str, str]:
    """Replace path parameters with examples and return both resolved path and parameter docs."""
    resolved_path = path
    param_docs = []
    
    for param in param_info.get('path', []):
        param_name = param['name']
        example_value = param['example']
        
        if example_value is not None:
            resolved_path = resolved_path.replace(f'{{{param_name}}}', str(example_value))
            param_docs.append(f"  # {param_name}: {param['description']} (required: {param['required']})")
    
    return resolved_path, '\n'.join(param_docs)


def generate_multipart_form_example(schema: Dict[str, Any], openapi_spec: Dict[str, Any] = None) -> List[str]:
    """Generate curl form data parameters for multipart/form-data requests."""
    form_parts = []
    
    if not isinstance(schema, dict):
        return form_parts
    
    # Resolve schema references
    if openapi_spec:
        schema = resolve_schema_ref(openapi_spec, schema)
    
    properties = schema.get('properties', {})
    
    for field_name, field_schema in properties.items():
        field_type = field_schema.get('type', 'string')
        field_format = field_schema.get('format', '')
        
        # Generate example value
        example_value = get_realistic_example_value(field_schema, field_name, openapi_spec)
        
        if field_format == 'binary' or 'file' in field_name.lower():
            # File upload field
            form_parts.append(f'-F "{field_name}=@/path/to/{field_name}.mp4"')
        elif field_type == 'string' and example_value:
            form_parts.append(f'-F "{field_name}={example_value}"')
        elif example_value is not None:
            form_parts.append(f'-F "{field_name}={example_value}"')
    
    return form_parts


def generate_comprehensive_curl_content(openapi_spec: Dict[str, Any], path: str, method: str, base_url: str = "https://api.example.com") -> str:
    """Generate comprehensive curl file content with full API context."""
    
    # Get all information
    operation_info = get_operation_info(openapi_spec, path, method)
    param_info = get_parameter_info(openapi_spec, path, method)
    request_body_info = get_request_body_info(openapi_spec, path, method)
    response_info = get_response_info(openapi_spec, path, method)
    
    # Resolve path parameters
    resolved_path, path_param_docs = resolve_path_with_examples(path, param_info)
    full_url = f"{base_url.rstrip('/')}{resolved_path}"
    
    content_lines = []
    
    # Header with endpoint information
    content_lines.extend([
        "=" * 80,
        f"ENDPOINT: {method.upper()} {path}",
        "=" * 80,
        f"Summary: {operation_info['summary']}",
        f"Description: {operation_info['description']}",
    ])
    
    if operation_info['tags']:
        content_lines.append(f"Tags: {', '.join(operation_info['tags'])}")
    
    if operation_info['deprecated']:
        content_lines.append("⚠️  DEPRECATED: This endpoint is deprecated")
    
    content_lines.append("")
    
    # Path Parameters Documentation
    if param_info['path']:
        content_lines.extend([
            "PATH PARAMETERS:",
            "-" * 40
        ])
        for param in param_info['path']:
            required_text = "REQUIRED" if param['required'] else "optional"
            content_lines.extend([
                f"• {param['name']} ({required_text})",
                f"  Description: {param['description']}",
                f"  Type: {param['schema'].get('type', 'unknown')}",
                f"  Example: {param['example']}",
                ""
            ])
    
    # Query Parameters Documentation
    if param_info['query']:
        content_lines.extend([
            "QUERY PARAMETERS:",
            "-" * 40
        ])
        for param in param_info['query']:
            required_text = "REQUIRED" if param['required'] else "optional"
            content_lines.extend([
                f"• {param['name']} ({required_text})",
                f"  Description: {param['description']}",
                f"  Type: {param['schema'].get('type', 'unknown')}",
                f"  Example: {param['example']}",
                ""
            ])
    
    # Request Body Documentation
    if request_body_info and method.upper() in ['POST', 'PUT', 'PATCH']:
        content_lines.extend([
            "REQUEST BODY:",
            "-" * 40,
            f"Description: {request_body_info['description']}",
            f"Required: {'Yes' if request_body_info['required'] else 'No'}",
            ""
        ])
        
        for content_type, content_data in request_body_info['content_types'].items():
            schema = content_data.get('schema', {})
            
            content_lines.extend([
                f"Content-Type: {content_type}",
                "Field Structure:",
            ])
            
            # Add detailed schema structure
            schema_lines = get_schema_structure(schema, openapi_spec=openapi_spec)
            content_lines.extend(schema_lines)
            
            content_lines.extend([
                "",
                "Example JSON:",
                json.dumps(content_data['example'], indent=2) if content_data['example'] else "No example available",
                ""
            ])
    
    # Response Documentation
    if response_info:
        content_lines.extend([
            "RESPONSES:",
            "-" * 40
        ])
        
        for status_code, response_data in response_info.items():
            content_lines.extend([
                f"Status {status_code}: {response_data['description']}",
                ""
            ])
            
            for content_type, content_data in response_data['content'].items():
                schema = content_data.get('schema', {})
                
                content_lines.extend([
                    f"  Content-Type: {content_type}",
                    f"  Response Structure:",
                ])
                
                # Add detailed schema structure with indentation
                schema_lines = get_schema_structure(schema, indent=1, openapi_spec=openapi_spec)
                content_lines.extend(schema_lines)
                
                content_lines.extend([
                    f"  Example Response:",
                    "  " + json.dumps(content_data['example'], indent=2).replace('\n', '\n  ') if content_data['example'] else "  No example available",
                    ""
                ])
    
    # Determine primary content type for the curl command
    primary_content_type = "application/json"  # Default
    is_multipart = False
    
    if request_body_info:
        content_types = list(request_body_info['content_types'].keys())
        if content_types:
            primary_content_type = content_types[0]
            is_multipart = 'multipart/form-data' in primary_content_type
    
    # Basic curl command
    content_lines.extend([
        "BASIC CURL COMMAND:",
        "-" * 40
    ])
    
    curl_parts = [
        f"curl -X {method.upper()}",
        f'"{full_url}"'
    ]
    
    # Add authorization header
    curl_parts.append('-H "Authorization: Bearer YOUR_TOKEN_HERE"')
    
    # Add query parameters example
    if param_info['query']:
        query_params = []
        for param in param_info['query']:
            if param['example'] is not None:
                query_params.append(f"{param['name']}={param['example']}")
        
        if query_params:
            if '?' not in full_url:
                full_url += '?' + '&'.join(query_params)
            curl_parts[1] = f'"{full_url}"'
    
    # Handle request body based on content type
    if request_body_info and method.upper() in ['POST', 'PUT', 'PATCH']:
        if is_multipart:
            # For multipart/form-data, don't set Content-Type header (curl will set it automatically with boundary)
            schema = request_body_info['content_types'][primary_content_type].get('schema', {})
            form_parts = generate_multipart_form_example(schema, openapi_spec)
            curl_parts.extend(form_parts)
        else:
            # For JSON or other content types
            curl_parts.append(f'-H "Content-Type: {primary_content_type}"')
            json_content = request_body_info['content_types'].get(primary_content_type)
            if json_content and json_content['example']:
                body_json = json.dumps(json_content['example'], separators=(',', ':'))
                curl_parts.append(f"-d '{body_json}'")
    elif not request_body_info and method.upper() in ['POST', 'PUT', 'PATCH']:
        # Default content type for methods that typically have bodies
        curl_parts.append(f'-H "Content-Type: {primary_content_type}"')
    
    curl_command = " \\\n  ".join(curl_parts)
    content_lines.append(curl_command)
    
    # Advanced curl examples
    content_lines.extend([
        "",
        "",
        "ADVANCED USAGE EXAMPLES:",
        "-" * 40
    ])
    
    # With verbose output
    content_lines.extend([
        "# With verbose output and response headers:",
        curl_command.replace("curl -X", "curl -v -X"),
        ""
    ])
    
    # Save response to file
    content_lines.extend([
        "# Save response to file:",
        curl_command + " \\\n  -o response_output.json",
        ""
    ])
    
    # With timing information
    content_lines.extend([
        "# With timing information:",
        curl_command + " \\\n  -w \"Total time: %{time_total}s\"",
        ""
    ])
    
    # Content-type specific examples
    if request_body_info:
        content_lines.extend([
            "CONTENT-TYPE SPECIFIC EXAMPLES:",
            "-" * 40
        ])
        
        for content_type, content_data in request_body_info['content_types'].items():
            content_lines.append(f"# For {content_type}:")
            
            if 'multipart/form-data' in content_type:
                multipart_curl = [
                    f"curl -X {method.upper()}",
                    f'"{full_url}"',
                    '-H "Authorization: Bearer YOUR_TOKEN_HERE"'
                ]
                
                schema = content_data.get('schema', {})
                form_parts = generate_multipart_form_example(schema, openapi_spec)
                multipart_curl.extend(form_parts)
                
                content_lines.append(" \\\n  ".join(multipart_curl))
            else:
                json_curl = [
                    f"curl -X {method.upper()}",
                    f'"{full_url}"',
                    f'-H "Content-Type: {content_type}"',
                    '-H "Authorization: Bearer YOUR_TOKEN_HERE"'
                ]
                
                if content_data['example']:
                    body_json = json.dumps(content_data['example'], separators=(',', ':'))
                    json_curl.append(f"-d '{body_json}'")
                
                content_lines.append(" \\\n  ".join(json_curl))
            
            content_lines.extend(["", ""])
    
    return '\n'.join(content_lines)


def sanitize_filename(method: str, path: str) -> str:
    """Convert method and path to a safe filename."""
    clean_path = re.sub(r'^/', '', path)
    clean_path = re.sub(r'[/{}\[\]<>:"|?*]', '_', clean_path)
    clean_path = re.sub(r'_+', '_', clean_path)
    clean_path = clean_path.strip('_')
    
    if not clean_path:
        clean_path = "root"
    
    return f"{method.upper()}__{clean_path}.txt"


def generate_all_endpoints_from_openapi(openapi_spec: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract all endpoints from OpenAPI specification."""
    endpoints = []
    
    paths = openapi_spec.get('paths', {})
    for path, path_item in paths.items():
        methods = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
        
        for method in methods:
            if method in path_item:
                endpoints.append({
                    'method': method.upper(),
                    'path': path
                })
    
    return endpoints


def create_enhanced_curl_files(openapi_file: str, api_diff_file: str, output_dir: str = "curl_files"):
    """Main function to create comprehensive curl files."""
    
    # Load OpenAPI specification
    print("Loading OpenAPI specification...")
    openapi_spec = load_openapi_spec(openapi_file)
    if not openapi_spec:
        print("Failed to load OpenAPI specification. Exiting.")
        return
    
    # Parse API diff text file
    print("Parsing API diff...")
    diff_data = parse_text_diff(api_diff_file)
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Get base URL from OpenAPI spec
    base_url = "https://api.example.com"
    if 'servers' in openapi_spec and openapi_spec['servers']:
        base_url = openapi_spec['servers'][0].get('url', base_url)
    
    print(f"Using base URL: {base_url}")
    
    # Generate comprehensive curl files for ALL endpoints
    print("Generating comprehensive curl files for all endpoints...")
    all_endpoints = generate_all_endpoints_from_openapi(openapi_spec)
    
    for endpoint in all_endpoints:
        method = endpoint['method']
        path = endpoint['path']
        
        print(f"Processing endpoint: {method} {path}")
        
        filename = sanitize_filename(method, path)
        filepath = Path(output_dir) / filename
        
        comprehensive_content = generate_comprehensive_curl_content(
            openapi_spec, path, method, base_url
        )
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(comprehensive_content)
        
        print(f"Created: {filepath}")
    
    # Process deleted endpoints - create simple deletion notice files
    print(f"\nProcessing deleted endpoints...")
    for endpoint in diff_data.get('deleted', []):
        method = endpoint.get('method', 'GET')
        path = endpoint.get('path', '/')
        
        print(f"Marking as deleted: {method} {path}")
        
        filename = sanitize_filename(method, path)
        filepath = Path(output_dir) / filename
        
        deletion_content = f"""================================================================================
DELETED ENDPOINT: {method.upper()} {path}
================================================================================

⚠️  API ENDPOINT REMOVED

This endpoint has been removed from the API and is no longer available.

Endpoint: {method.upper()} {path}
Status: DELETED
Date Removed: {endpoint.get('date_removed', 'Unknown')}

Please refer to the API documentation for alternative endpoints or contact 
the API maintainers for migration guidance.

================================================================================"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(deletion_content)
        
        print(f"Marked as deleted: {filepath}")
    
    added_count = len(diff_data.get('added', []))
    deleted_count = len(diff_data.get('deleted', []))
    modified_count = len(diff_data.get('modified', []))
    summary_content = [
        "API ENDPOINTS SUMMARY",
        "=" * 50,
        f"Total active endpoints: {len(all_endpoints)}",
        f"Added endpoints: {added_count}",
        f"Modified endpoints: {modified_count}",
        f"Deleted endpoints: {deleted_count}",
        f"Base URL: {base_url}",
        "",
        "Endpoints by method:",
    ]
    
    # Group by method
    method_groups = {}
    for endpoint in all_endpoints:
        method = endpoint['method']
        if method not in method_groups:
            method_groups[method] = []
        method_groups[method].append(endpoint['path'])
    
    for method, paths in sorted(method_groups.items()):
        summary_content.extend([
            f"  {method}: {len(paths)} endpoints",
            *[f"    - {path}" for path in sorted(paths)],
            ""
        ])
    
    # Add deleted endpoints section
    if diff_data.get('deleted'):
        summary_content.extend([
            "DELETED ENDPOINTS:",
            "-" * 20
        ])
        for endpoint in diff_data['deleted']:
            summary_content.append(f"  {endpoint['method']} {endpoint['path']}")
        summary_content.append("")

    if diff_data.get('added'):
        summary_content.extend([
            "ADDED ENDPOINTS:",
            "-" * 20
        ])
        for endpoint in diff_data['added']:
            summary_content.append(f"  {endpoint['method']} {endpoint['path']}")
        summary_content.append("")

    if diff_data.get('modified'):
        summary_content.extend([
            "MODIFIED ENDPOINTS:",
            "-" * 20
        ])
        for endpoint in diff_data['modified']:
            summary_content.append(f"  {endpoint['method']} {endpoint['path']}")
        summary_content.append("")

    # Write summary file
    summary_file = Path(output_dir) / "summary.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary_content))
    
    print(f"\n" + "="*50)
    print(f"Summary:")
    print(f"  Total active endpoints processed: {len(all_endpoints)}")
    print(f"  Added: {added_count}")
    print(f"  Modified: {modified_count}")
    print(f"  Deleted endpoints marked: {deleted_count}")
    print(f"  Files created in '{output_dir}' directory")
    print(f"  Summary file: {summary_file}")
    print(f"="*50)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate comprehensive curl files from OpenAPI spec")
    parser.add_argument("openapi_file", help="Path to OpenAPI YAML file")
    parser.add_argument("api_diff_file", help="Path to API diff text file")
    parser.add_argument("-o", "--output", default="curl_files", help="Output directory (default: curl_files)")
    parser.add_argument("--base-url", help="Base URL for API calls (overrides OpenAPI servers)")
    
    args = parser.parse_args()
    
    create_enhanced_curl_files(args.openapi_file, args.api_diff_file, args.output)