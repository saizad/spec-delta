#!/usr/bin/env python3
"""
API Endpoint Logs to Markdown Converter
Converts API endpoint log files to a formatted Markdown documentation file.
"""

import re
from pathlib import Path
from typing import Dict, List


class EndpointLogParser:
    def __init__(self):
        self.endpoint_data = {}
    
    def parse_file(self, file_path: str) -> Dict:
        """Parse a single endpoint log file and extract structured data."""
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        data = {
            'filename': Path(file_path).name,
            'endpoint': '',
            'method': '',
            'path': '',
            'summary': '',
            'description': '',
            'tags': '',
            'path_parameters': [],
            'query_parameters': [],
            'request_body': [],
            'responses': [],
            'curl_examples': []
        }
        
        # Extract endpoint information
        endpoint_match = re.search(r'ENDPOINT: (\w+) (.+)', content)
        if endpoint_match:
            data['method'] = endpoint_match.group(1)
            data['path'] = endpoint_match.group(2)
            data['endpoint'] = f"{data['method']} {data['path']}"
        
        # Extract summary
        summary_match = re.search(r'Summary: (.+)', content)
        if summary_match:
            data['summary'] = summary_match.group(1).strip()
        
        # Extract description
        desc_match = re.search(r'Description: (.+?)(?=Tags:|PATH PARAMETERS:|QUERY PARAMETERS:|RESPONSES:|$)', content, re.DOTALL)
        if desc_match:
            data['description'] = desc_match.group(1).strip()
        
        # Extract tags
        tags_match = re.search(r'Tags: (.+)', content)
        if tags_match:
            data['tags'] = tags_match.group(1).strip()
        
        # Extract path parameters
        path_params_section = re.search(r'PATH PARAMETERS:\s*-{40}\s*(.*?)(?=QUERY PARAMETERS:|RESPONSES:|BASIC CURL COMMAND:|$)', content, re.DOTALL)
        if path_params_section:
            data['path_parameters'] = self._parse_parameters(path_params_section.group(1))
        
        # Extract query parameters
        query_params_section = re.search(r'QUERY PARAMETERS:\s*-{40}\s*(.*?)(?=REQUEST BODY:|RESPONSES:|BASIC CURL COMMAND:|$)', content, re.DOTALL)
        if query_params_section:
            data['query_parameters'] = self._parse_parameters(query_params_section.group(1))
        
        # Extract request body
        request_body_section = re.search(r'REQUEST BODY:\s*-{40}\s*(.*?)(?=RESPONSES:|BASIC CURL COMMAND:|$)', content, re.DOTALL)
        if request_body_section:
            data['request_body'] = self._parse_request_body(request_body_section.group(1))
        
        # Extract responses
        responses_section = re.search(r'RESPONSES:\s*-{40}\s*(.*?)(?=BASIC CURL COMMAND:|$)', content, re.DOTALL)
        if responses_section:
            data['responses'] = self._parse_responses(responses_section.group(1))
        
        # Extract curl examples
        curl_section = re.search(r'BASIC CURL COMMAND:\s*-{40}\s*(.*?)(?=ADVANCED USAGE EXAMPLES:|$)', content, re.DOTALL)
        if curl_section:
            data['curl_examples'].append({
                'title': 'Basic Command',
                'command': curl_section.group(1).strip()
            })
        
        advanced_curl_section = re.search(r'ADVANCED USAGE EXAMPLES:\s*-{40}\s*(.*)', content, re.DOTALL)
        if advanced_curl_section:
            advanced_examples = self._parse_advanced_curl(advanced_curl_section.group(1))
            data['curl_examples'].extend(advanced_examples)
        
        return data
    
    def _parse_parameters(self, params_text: str) -> List[Dict]:
        """Parse parameter sections."""
        parameters = []
        param_blocks = re.split(r'•\s+', params_text)
        
        for block in param_blocks:
            if not block.strip():
                continue
            
            param = {}
            lines = block.strip().split('\n')
            
            # Extract parameter name and required status
            first_line = lines[0].strip()
            if '(' in first_line:
                name_part = first_line.split('(')[0].strip()
                required_part = first_line.split('(')[1].split(')')[0].strip()
                param['name'] = name_part
                param['required'] = required_part.upper() == 'REQUIRED'
            else:
                param['name'] = first_line
                param['required'] = False
            
            # Extract other details with multi-line support
            current_field = None
            current_content = []
            
            for line in lines[1:]:
                line_stripped = line.strip()
                
                if line_stripped.startswith('Description:'):
                    if current_field:
                        param[current_field] = '\n'.join(current_content).strip()
                    current_field = 'description'
                    current_content = [line_stripped.replace('Description:', '').strip()]
                elif line_stripped.startswith('Type:'):
                    if current_field:
                        param[current_field] = '\n'.join(current_content).strip()
                    current_field = 'type'
                    current_content = [line_stripped.replace('Type:', '').strip()]
                elif line_stripped.startswith('Example:'):
                    if current_field:
                        param[current_field] = '\n'.join(current_content).strip()
                    current_field = 'example'
                    current_content = [line_stripped.replace('Example:', '').strip()]
                elif current_field and line_stripped:
                    # Continue multi-line content
                    current_content.append(line_stripped)
            
            # Add the last field
            if current_field:
                param[current_field] = '\n'.join(current_content).strip()
            
            parameters.append(param)
        
        return parameters
    
    def _parse_request_body(self, request_body_text: str) -> List[Dict]:
        """Parse request body section with multiple content types."""
        request_bodies = []
        
        # Extract basic info first
        description_match = re.search(r'Description: (.+)', request_body_text)
        required_match = re.search(r'Required: (.+)', request_body_text)
        
        base_description = description_match.group(1).strip() if description_match else ""
        is_required = required_match.group(1).strip().lower() == 'yes' if required_match else False
        
        # Split by Content-Type sections
        content_type_sections = re.split(r'Content-Type: (.+)', request_body_text)
        
        # Process each content type section
        for i in range(1, len(content_type_sections), 2):
            if i + 1 < len(content_type_sections):
                content_type = content_type_sections[i].strip()
                section_content = content_type_sections[i + 1]
                
                request_body = {
                    'description': base_description,
                    'required': is_required,
                    'content_type': content_type,
                    'fields': [],
                    'example': ''
                }
                
                # Extract field structure
                if 'Field Structure:' in section_content:
                    field_section = section_content.split('Field Structure:')[1]
                    if 'Example JSON:' in field_section:
                        field_section = field_section.split('Example JSON:')[0]
                    
                    request_body['fields'] = self._parse_field_structure(field_section)
                
                # Extract example JSON
                if 'Example JSON:' in section_content:
                    json_example = self._extract_complete_json(section_content, 'Example JSON:')
                    if json_example:
                        request_body['example'] = json_example
                    else:
                        # Fallback extraction
                        example_section = section_content.split('Example JSON:')[1].strip()
                        # Take content until next Content-Type or end
                        next_content_type = re.search(r'\nContent-Type:', example_section)
                        if next_content_type:
                            request_body['example'] = example_section[:next_content_type.start()].strip()
                        else:
                            request_body['example'] = example_section.strip()
                
                request_bodies.append(request_body)
        
        return request_bodies
    
    def _parse_field_structure(self, field_text: str) -> List[Dict]:
        """Parse field structure from request body."""
        fields = []
        lines = field_text.strip().split('\n')
        
        current_field = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if it's a field definition (no leading spaces in original)
            if not line.startswith('  ') and ':' in line:
                # Save previous field
                if current_field:
                    fields.append(current_field)
                
                # Parse new field
                parts = line.split(':', 1)
                field_name = parts[0].strip()
                field_info = parts[1].strip() if len(parts) > 1 else ''
                
                current_field = {
                    'name': field_name,
                    'type': '',
                    'format': '',
                    'required': False,
                    'description': ''
                }
                
                # Parse field info like "string (required)" or "string (format: uuid) (required)"
                if field_info:
                    # Extract type
                    type_match = re.match(r'([^(]+)', field_info)
                    if type_match:
                        current_field['type'] = type_match.group(1).strip()
                    
                    # Check if required
                    if '(required)' in field_info:
                        current_field['required'] = True
                    elif '(optional)' in field_info:
                        current_field['required'] = False
                    
                    # Extract format
                    format_match = re.search(r'\(format: ([^)]+)\)', field_info)
                    if format_match:
                        current_field['format'] = format_match.group(1).strip()
            
            elif line.startswith('  ') and current_field:
                # This is additional info for the current field (like nested object details)
                if not current_field['description']:
                    current_field['description'] = line.strip()
                else:
                    current_field['description'] += ' ' + line.strip()
        
        # Add the last field
        if current_field:
            fields.append(current_field)
        
        return fields
    
    def _extract_complete_json(self, text: str, start_marker: str) -> str:
        """Extract complete JSON object with proper brace matching."""
        start_index = text.find(start_marker)
        if start_index == -1:
            return ""
        
        # Find the start of JSON (first '{')
        json_start = text.find('{', start_index)
        if json_start == -1:
            return ""
        
        # Count braces to find the complete JSON
        brace_count = 0
        json_end = json_start
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text[json_start:], json_start):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i
                        break
        
        if brace_count == 0:
            return text[json_start:json_end + 1]
        
        return ""
    
    def _parse_responses(self, responses_text: str) -> List[Dict]:
        """Parse response sections with improved JSON extraction."""
        responses = []
        
        # Split by status codes
        status_blocks = re.split(r'Status (\d+):', responses_text)
        
        for i in range(1, len(status_blocks), 2):
            if i + 1 < len(status_blocks):
                status_code = status_blocks[i]
                content = status_blocks[i + 1]
                
                response = {
                    'status': status_code,
                    'description': '',
                    'content_type': '',
                    'schema': {},
                    'example': ''
                }
                
                # Check if it's just "No response body"
                if 'No response body' in content:
                    response['description'] = 'No response body'
                else:
                    # Extract content type
                    content_type_match = re.search(r'Content-Type: (.+)', content)
                    if content_type_match:
                        response['content_type'] = content_type_match.group(1).strip()
                    
                    # Extract example response with proper JSON handling
                    if 'Example Response:' in content:
                        json_example = self._extract_complete_json(content, 'Example Response:')
                        if json_example:
                            response['example'] = json_example
                        else:
                            # Fallback to simpler extraction if JSON parsing fails
                            example_section = content.split('Example Response:')[1].strip()
                            # Take everything until next major section or end
                            next_section = re.search(r'\n\n[A-Z]', example_section)
                            if next_section:
                                response['example'] = example_section[:next_section.start()].strip()
                            else:
                                response['example'] = example_section.strip()
                    
                    # Extract response structure (simplified)
                    if 'Response Structure:' in content:
                        structure_section = content.split('Response Structure:')[1]
                        if 'Example Response:' in structure_section:
                            structure_section = structure_section.split('Example Response:')[0]
                        response['schema'] = structure_section.strip()
                
                responses.append(response)
        
        return responses
    
    def _parse_advanced_curl(self, curl_text: str) -> List[Dict]:
        """Parse advanced curl examples."""
        examples = []
        
        # Split by comments (lines starting with #)
        sections = re.split(r'# (.+):', curl_text)
        
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                title = sections[i].strip()
                command = sections[i + 1].strip()
                
                examples.append({
                    'title': title,
                    'command': command
                })
        
        return examples


class MarkdownGenerator:
    def __init__(self):
        pass
    
    def generate_single_endpoint_markdown(self, endpoint: Dict) -> str:
        """Generate markdown documentation for a single endpoint."""
        sections = []
        
        # Add title
        sections.append(f"# {endpoint['endpoint']}")
        sections.append("")
        
        # Basic info table
        info_table = []
        info_table.append("## Overview")
        info_table.append("")
        info_table.append("| Property | Value |")
        info_table.append("|----------|-------|")
        info_table.append(f"| **Method** | `{endpoint['method']}` |")
        info_table.append(f"| **Path** | `{endpoint['path']}` |")
        if endpoint['tags']:
            info_table.append(f"| **Tags** | {endpoint['tags']} |")
        if endpoint['summary'] and endpoint['summary'] != 'No summary available':
            info_table.append(f"| **Summary** | {endpoint['summary']} |")
        
        sections.extend(info_table)
        sections.append("")
        
        # Description
        if endpoint['description']:
            sections.append(f"## Description")
            sections.append("")
            sections.append(endpoint['description'])
            sections.append("")
        
        # Path Parameters
        if endpoint['path_parameters']:
            sections.append("## Path Parameters")
            sections.append("")
            sections.append(self._generate_parameters_table(endpoint['path_parameters']))
            sections.append("")
        
        # Query Parameters
        if endpoint['query_parameters']:
            sections.append("## Query Parameters")
            sections.append("")
            sections.append(self._generate_parameters_table(endpoint['query_parameters']))
            sections.append("")
        
        # Request Body
        if endpoint['request_body']:
            sections.append("## Request Body")
            sections.append("")
            for request_body in endpoint['request_body']:
                sections.append(self._generate_request_body_section(request_body))
                sections.append("")
        
        # Responses
        if endpoint['responses']:
            sections.append("## Responses")
            sections.append("")
            for response in endpoint['responses']:
                sections.append(self._generate_response_section(response))
                sections.append("")
        
        # cURL Examples
        if endpoint['curl_examples']:
            sections.append("## cURL Examples")
            sections.append("")
            for example in endpoint['curl_examples']:
                sections.append(f"### {example['title']}")
                sections.append("")
                sections.append(f"```bash\n{example['command']}\n```")
                sections.append("")
        
        return '\n'.join(sections)
    
    def _generate_request_body_section(self, request_body: Dict) -> str:
        """Generate markdown section for request body."""
        sections = []
        
        # Content type header
        sections.append(f"### {request_body['content_type']}")
        sections.append("")
        
        # Basic info
        info_table = []
        info_table.append("| Property | Value |")
        info_table.append("|----------|-------|")
        info_table.append(f"| **Required** | {'Yes' if request_body['required'] else 'No'} |")
        if request_body['description'] and request_body['description'] != 'No description available':
            info_table.append(f"| **Description** | {request_body['description']} |")
        
        sections.extend(info_table)
        sections.append("")
        
        # Field structure
        if request_body['fields']:
            sections.append("**Field Structure:**")
            sections.append("")
            sections.append(self._generate_request_body_fields_table(request_body['fields']))
            sections.append("")
        
        # Example
        if request_body['example']:
            sections.append("**Example:**")
            sections.append("")
            sections.append(f"```json\n{request_body['example']}\n```")
            sections.append("")
        
        return '\n'.join(sections)
    
    def _generate_request_body_fields_table(self, fields: List[Dict]) -> str:
        """Generate a markdown table for request body fields."""
        if not fields:
            return ""
        
        table = []
        table.append("| Field | Type | Format | Required | Description |")
        table.append("|-------|------|--------|----------|-------------|")
        
        for field in fields:
            name = field.get('name', '')
            field_type = field.get('type', '')
            field_format = field.get('format', '')
            required = '✓' if field.get('required', False) else ''
            description = field.get('description', '')
            
            # Handle special formatting for nested fields
            if field_type.startswith('array of'):
                field_type = f"`{field_type}`"
            elif field_type == 'unknown':
                field_type = 'object'
            
            table.append(f"| `{name}` | {field_type} | {field_format} | {required} | {description} |")
        
        return '\n'.join(table)
    
    def generate_markdown(self, endpoints_data: List[Dict]) -> str:
        """Generate a complete Markdown documentation from parsed endpoint data."""
        md_content = []
        
        # Add title and table of contents
        md_content.append("# API Documentation\n")
        md_content.append("## Table of Contents\n")
        
        for i, endpoint in enumerate(endpoints_data, 1):
            anchor = self._create_anchor(endpoint['endpoint'])
            md_content.append(f"{i}. [{endpoint['endpoint']}](#{anchor})")
        
        md_content.append("\n---\n")
        
        # Generate documentation for each endpoint
        for endpoint in endpoints_data:
            md_content.append(self._generate_endpoint_section(endpoint))
        
        return '\n'.join(md_content)
    
    def _create_anchor(self, text: str) -> str:
        """Create a markdown anchor from text."""
        return re.sub(r'[^\w\s-]', '', text.lower()).replace(' ', '-')
    
    def _generate_endpoint_section(self, endpoint: Dict) -> str:
        """Generate markdown section for a single endpoint."""
        sections = []
        
        # Endpoint title
        sections.append(f"## {endpoint['endpoint']}")
        
        # Basic info table
        info_table = []
        info_table.append("| Property | Value |")
        info_table.append("|----------|-------|")
        info_table.append(f"| **Method** | `{endpoint['method']}` |")
        info_table.append(f"| **Path** | `{endpoint['path']}` |")
        if endpoint['tags']:
            info_table.append(f"| **Tags** | {endpoint['tags']} |")
        if endpoint['summary'] and endpoint['summary'] != 'No summary available':
            info_table.append(f"| **Summary** | {endpoint['summary']} |")
        
        sections.append('\n'.join(info_table))
        
        # Description
        if endpoint['description']:
            sections.append(f"\n### Description\n{endpoint['description']}")
        
        # Path Parameters
        if endpoint['path_parameters']:
            sections.append("\n### Path Parameters")
            sections.append(self._generate_parameters_table(endpoint['path_parameters']))
        
        # Query Parameters
        if endpoint['query_parameters']:
            sections.append("\n### Query Parameters")
            sections.append(self._generate_parameters_table(endpoint['query_parameters']))
        
        # Responses
        if endpoint['responses']:
            sections.append("\n### Responses")
            for response in endpoint['responses']:
                sections.append(self._generate_response_section(response))
        
        # cURL Examples
        if endpoint['curl_examples']:
            sections.append("\n### cURL Examples")
            for example in endpoint['curl_examples']:
                sections.append(f"\n#### {example['title']}")
                sections.append(f"```bash\n{example['command']}\n```")
        
        sections.append("\n---\n")
        
        return '\n'.join(sections)
    
    def _generate_parameters_table(self, parameters: List[Dict]) -> str:
        """Generate a markdown table for parameters."""
        if not parameters:
            return ""
        
        table = []
        table.append("| Name | Type | Required | Description | Example |")
        table.append("|------|------|----------|-------------|---------|")
        
        for param in parameters:
            name = param.get('name', '')
            param_type = param.get('type', '')
            required = '✓' if param.get('required', False) else ''
            description = param.get('description', 'No description available')
            example = param.get('example', '')
            
            # Handle multi-line descriptions with option lists
            if description and '\n' in description:
                # Convert multi-line descriptions to proper markdown format
                desc_lines = description.split('\n')
                formatted_desc = []
                
                for line in desc_lines:
                    line = line.strip()
                    if line.startswith('* `') and '` -' in line:
                        # Format option lines like: * `1` - Bring To School
                        formatted_desc.append(f"<br>• {line[2:]}")  # Remove '* ' and add bullet
                    elif line.startswith('*'):
                        formatted_desc.append(f"<br>• {line[2:]}")  # Remove '* ' and add bullet
                    elif line:
                        if not formatted_desc:
                            formatted_desc.append(line)
                        else:
                            formatted_desc.append(f"<br>{line}")
                
                description = ''.join(formatted_desc)
            
            # Escape pipe characters in table cells
            description = description.replace('|', '\\|')
            example = str(example).replace('|', '\\|')
            
            table.append(f"| `{name}` | {param_type} | {required} | {description} | {example} |")
        
        return '\n'.join(table)
    
    def _generate_response_section(self, response: Dict) -> str:
        """Generate markdown section for a response."""
        sections = []
        
        sections.append(f"\n#### Status {response['status']}")
        
        if response['description']:
            sections.append(response['description'])
        
        if response['content_type']:
            sections.append(f"**Content-Type:** `{response['content_type']}`")
        
        if response['schema']:
            sections.append("**Response Schema:**")
            sections.append(f"```\n{response['schema']}\n```")
        
        if response['example']:
            sections.append("**Example Response:**")
            sections.append(f"```json\n{response['example']}\n```")
        
        return '\n'.join(sections)


def convert_logs_to_markdown(input_directory: str, output_directory: str = None):
    """Main function to convert all endpoint log files to separate markdown files."""
    parser = EndpointLogParser()
    generator = MarkdownGenerator()
    
    # Use input directory as output directory if not specified
    if output_directory is None:
        output_directory = input_directory
    
    # Find all .txt files in the input directory
    input_path = Path(input_directory)
    output_path = Path(output_directory)
    txt_files = list(input_path.glob('*.txt'))
    
    if not txt_files:
        print(f"No .txt files found in {input_directory}")
        return
    
    print(f"Found {len(txt_files)} endpoint log files")
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    processed_count = 0
    failed_count = 0
    
    # Process each file separately
    for file_path in txt_files:
        print(f"Processing: {file_path.name}")
        try:
            # Parse the individual file
            endpoint_data = parser.parse_file(str(file_path))
            
            # Generate markdown for single endpoint
            markdown_content = generator.generate_single_endpoint_markdown(endpoint_data)
            
            # Create output filename (replace .txt with .md)
            output_filename = file_path.stem + '.md'
            output_file_path = output_path / output_filename
            
            # Write to individual markdown file
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            print(f"  → Generated: {output_file_path.name}")
            processed_count += 1
            
        except Exception as e:
            print(f"  ✗ Error processing {file_path.name}: {e}")
            failed_count += 1
    
    print(f"\n✓ Conversion completed!")
    print(f"  • Processed: {processed_count} files")
    print(f"  • Failed: {failed_count} files")
    print(f"  • Output directory: {output_path.absolute()}")


if __name__ == "__main__":
    import sys
    
    # Get input directory from command line argument or use current directory
    input_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_logs_to_markdown(input_dir, output_dir)