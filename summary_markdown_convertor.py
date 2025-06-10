#!/usr/bin/env python3
"""
API Endpoints Report Beautifier

A professional tool to convert API endpoint summaries into beautifully formatted Markdown reports.
Supports various customization options for professional documentation.


"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class EndpointInfo:
    """Data class to store endpoint information"""
    method: str
    path: str
    description: Optional[str] = None


@dataclass
class APIReport:
    """Data class to store complete API report information"""
    total_endpoints: int
    added_endpoints_count: int
    modified_endpoints_count: int
    deleted_endpoints_count: int
    base_url: str
    endpoints_by_method: Dict[str, List[str]]
    deleted_endpoints: List[str]
    added_endpoints: List[str]
    modified_endpoints: List[str]


class APIBeautifier:
    """Professional API documentation beautifier"""
    
    def __init__(self, 
                 include_toc: bool = True,
                 include_summary: bool = True,
                 include_badges: bool = True,
                 sort_endpoints: bool = True,
                 group_by_category: bool = False,
                 add_timestamps: bool = True,
                 custom_title: Optional[str] = None,
                 output_format: str = 'github',
                 github_base_url: Optional[str] = None,
                 github_branch: str = 'main'):
        """
        Initialize the beautifier with configuration options
        
        Args:
            include_toc: Include table of contents
            include_summary: Include executive summary
            include_badges: Include status badges
            sort_endpoints: Sort endpoints alphabetically
            group_by_category: Group endpoints by category (experimental)
            add_timestamps: Add generation timestamp
            custom_title: Custom title for the report
            output_format: Output format ('github', 'gitlab', 'generic')
            github_base_url: Base GitHub URL for hyperlinks (e.g., 'https://github.com/user/repo/blob')
            github_branch: GitHub branch name for hyperlinks
        """
        self.include_toc = include_toc
        self.include_summary = include_summary
        self.include_badges = include_badges
        self.sort_endpoints = sort_endpoints
        self.group_by_category = group_by_category
        self.add_timestamps = add_timestamps
        self.custom_title = custom_title or "API Endpoints Documentation"
        self.output_format = output_format
        self.github_base_url = github_base_url
        self.github_branch = github_branch
        
    def _endpoint_to_filename(self, method: str, endpoint: str) -> str:
        """
        Convert HTTP method and endpoint path to filename format
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: Endpoint path (e.g., /content/topics/{topic_id}/videos/upload/)
            
        Returns:
            Filename string (e.g., POST__content_topics_topic_id_videos_upload.txt)
        """
        # Remove leading slash
        path = endpoint.lstrip('/')
        
        # Replace path separators with underscores
        path = path.replace('/', '_')
        
        # Replace curly braces (path parameters) with underscores
        path = re.sub(r'[{}]', '_', path)
        
        # Replace other special characters with underscores
        path = re.sub(r'[^\w]', '_', path)
        
        # Remove trailing underscores and clean up multiple underscores
        path = re.sub(r'_+', '_', path).strip('_')
        
        # Construct filename
        filename = f"{method}__{path}.txt"
        
        return filename
    
    def _create_endpoint_link(self, method: str, endpoint: str) -> str:
        """
        Create a hyperlinked endpoint or plain text if no GitHub URL provided
        
        Args:
            method: HTTP method
            endpoint: Endpoint path
            
        Returns:
            Markdown formatted link or plain text
        """
        if self.github_base_url:
            filename = self._endpoint_to_filename(method, endpoint)
            full_url = f"{self.github_base_url}/{self.github_branch}/{filename}"
            return f"[`{endpoint}`]({full_url})"
        else:
            return f"`{endpoint}`"
    
    def parse_raw_text(self, raw_text: str) -> APIReport:
        """Parse raw API summary text into structured data"""
        lines = raw_text.strip().split('\n')
        
        # Extract basic info
        total_endpoints = 0
        added_endpoints = 0
        modified_endpoints = 0
        deleted_endpoints = 0
        base_url = ""
        
        endpoints_by_method = defaultdict(list)
        deleted_list = []
        added_list = []
        modified_list = []
        
        current_section = None
        current_method = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Extract summary numbers
            if line.startswith("Total active endpoints:"):
                total_endpoints = int(re.search(r'\d+', line).group())
            elif line.startswith("Added endpoints:"):
                added_endpoints = int(re.search(r'\d+', line).group())
            elif line.startswith("Modified endpoints:"):
                modified_endpoints = int(re.search(r'\d+', line).group())
            elif line.startswith("Deleted endpoints:"):
                deleted_endpoints = int(re.search(r'\d+', line).group())
            elif line.startswith("Base URL:"):
                base_url = line.split("Base URL: ")[1]
            
            # Track sections
            elif line == "DELETED ENDPOINTS:":
                current_section = "deleted"
                current_method = None
            elif line == "ADDED ENDPOINTS:":
                current_section = "added"
                current_method = None
            elif line == "MODIFIED ENDPOINTS:":
                current_section = "modified"
                current_method = None
            elif line.startswith("Endpoints by method:"):
                current_section = "methods"
                current_method = None
            
            # Parse method sections
            elif current_section == "methods" and ":" in line and "endpoints" in line:
                method_match = re.match(r'\s*(\w+):\s*(\d+)\s*endpoints?', line)
                if method_match:
                    current_method = method_match.group(1)
            elif current_section == "methods" and line.startswith("- /") and current_method:
                endpoint = line[2:].strip()  # Remove "- "
                endpoints_by_method[current_method].append(endpoint)
            
            # Parse change sections
            elif current_section in ["deleted", "added", "modified"] and line.startswith("- ") or \
                 (current_section in ["deleted", "added", "modified"] and 
                  re.match(r'\s*(GET|POST|PUT|DELETE|PATCH)\s+/', line)):
                endpoint = line.strip()
                if endpoint.startswith("- "):
                    endpoint = endpoint[2:]
                
                if current_section == "deleted":
                    deleted_list.append(endpoint)
                elif current_section == "added":
                    added_list.append(endpoint)
                elif current_section == "modified":
                    modified_list.append(endpoint)
        
        return APIReport(
            total_endpoints=total_endpoints,
            added_endpoints_count=added_endpoints,
            modified_endpoints_count=modified_endpoints,
            deleted_endpoints_count=deleted_endpoints,
            base_url=base_url,
            endpoints_by_method=dict(endpoints_by_method),
            deleted_endpoints=deleted_list,
            added_endpoints=added_list,
            modified_endpoints=modified_list
        )
    
    def _generate_badges(self, report: APIReport) -> str:
        """Generate status badges"""
        if not self.include_badges:
            return ""
            
        badges = []
        
        # Total endpoints badge
        badges.append(f"![Total Endpoints](https://img.shields.io/badge/Total%20Endpoints-{report.total_endpoints}-blue)")
        
        # Changes badges
        if report.added_endpoints_count > 0:
            badges.append(f"![Added](https://img.shields.io/badge/Added-{report.added_endpoints_count}-green)")
        
        if report.modified_endpoints_count > 0:
            badges.append(f"![Modified](https://img.shields.io/badge/Modified-{report.modified_endpoints_count}-yellow)")
            
        if report.deleted_endpoints_count > 0:
            badges.append(f"![Deleted](https://img.shields.io/badge/Deleted-{report.deleted_endpoints_count}-red)")
        
        return " ".join(badges) + "\n\n"
    
    def _generate_toc(self) -> str:
        """Generate table of contents"""
        if not self.include_toc:
            return ""
            
        toc = "## 📋 Table of Contents\n\n"
        toc += "- [Executive Summary](#executive-summary)\n"
        toc += "- [API Overview](#api-overview)\n"
        toc += "- [Endpoints by HTTP Method](#endpoints-by-http-method)\n"
        toc += "- [Recent Changes](#recent-changes)\n"
        toc += "  - [Added Endpoints](#added-endpoints)\n"
        toc += "  - [Modified Endpoints](#modified-endpoints)\n"
        toc += "  - [Deleted Endpoints](#deleted-endpoints)\n"
        if self.add_timestamps:
            toc += "- [Report Information](#report-information)\n"
        toc += "\n"
        
        return toc
    
    def _generate_summary(self, report: APIReport) -> str:
        """Generate executive summary"""
        if not self.include_summary:
            return ""
            
        summary = "## 📊 Executive Summary\n\n"
        summary += f"This API documentation covers **{report.total_endpoints}** active endpoints "
        summary += f"across **{len(report.endpoints_by_method)}** HTTP methods.\n\n"
        
        if any([report.added_endpoints_count, report.modified_endpoints_count, report.deleted_endpoints_count]):
            summary += "### Recent Changes\n\n"
            summary += f"- ✅ **{report.added_endpoints_count}** endpoints added\n"
            summary += f"- 🔄 **{report.modified_endpoints_count}** endpoints modified\n"
            summary += f"- ❌ **{report.deleted_endpoints_count}** endpoints deleted\n\n"
        
        return summary
    
    def _generate_overview(self, report: APIReport) -> str:
        """Generate API overview section"""
        overview = "## 🌐 API Overview\n\n"
        overview += f"**Base URL:** `{report.base_url}`\n\n"
        
        # Method distribution
        overview += "### HTTP Methods Distribution\n\n"
        overview += "| Method | Count | Percentage |\n"
        overview += "|--------|-------|------------|\n"
        
        total = sum(len(endpoints) for endpoints in report.endpoints_by_method.values())
        
        for method in sorted(report.endpoints_by_method.keys()):
            count = len(report.endpoints_by_method[method])
            percentage = (count / total * 100) if total > 0 else 0
            overview += f"| `{method}` | {count} | {percentage:.1f}% |\n"
        
        overview += "\n"
        return overview
    
    def _format_endpoint_list(self, endpoints: List[str], method: str = None) -> str:
        """Format a list of endpoints with hyperlinks"""
        if not endpoints:
            return "_No endpoints_\n\n"
            
        if self.sort_endpoints:
            endpoints = sorted(endpoints)
        
        formatted = ""
        for endpoint in endpoints:
            if method:
                # For method-specific sections, create hyperlink
                link = self._create_endpoint_link(method, endpoint)
                formatted += f"- **`{method}`** {link}\n"
            else:
                # For change sections, parse method from endpoint if present
                method_match = re.match(r'^(GET|POST|PUT|DELETE|PATCH)\s+(.+)$', endpoint)
                if method_match:
                    parsed_method = method_match.group(1)
                    parsed_path = method_match.group(2)
                    link = self._create_endpoint_link(parsed_method, parsed_path)
                    formatted += f"- **`{parsed_method}`** {link}\n"
                else:
                    # Fallback to plain text if method not found
                    formatted += f"- `{endpoint}`\n"
        
        return formatted + "\n"
    
    def _generate_endpoints_section(self, report: APIReport) -> str:
        """Generate endpoints by method section"""
        section = "## 🔌 Endpoints by HTTP Method\n\n"
        
        # Sort methods by common REST order
        method_order = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
        sorted_methods = []
        
        for method in method_order:
            if method in report.endpoints_by_method:
                sorted_methods.append(method)
        
        # Add any remaining methods
        for method in sorted(report.endpoints_by_method.keys()):
            if method not in sorted_methods:
                sorted_methods.append(method)
        
        for method in sorted_methods:
            endpoints = report.endpoints_by_method[method]
            method_emoji = {
                'GET': '📖', 'POST': '➕', 'PUT': '📝', 
                'PATCH': '🔧', 'DELETE': '❌'
            }.get(method, '🔗')
            
            section += f"### {method_emoji} {method} ({len(endpoints)} endpoints)\n\n"
            section += self._format_endpoint_list(endpoints, method)
        
        return section
    
    def _generate_changes_section(self, report: APIReport) -> str:
        """Generate recent changes section"""
        section = "## 🔄 Recent Changes\n\n"
        
        # Added endpoints
        section += "### ✅ Added Endpoints\n\n"
        if report.added_endpoints:
            section += self._format_endpoint_list(report.added_endpoints)
        else:
            section += "_No endpoints added_\n\n"
        
        # Modified endpoints  
        section += "### 🔄 Modified Endpoints\n\n"
        if report.modified_endpoints:
            section += self._format_endpoint_list(report.modified_endpoints)
        else:
            section += "_No endpoints modified_\n\n"
        
        # Deleted endpoints
        section += "### ❌ Deleted Endpoints\n\n"
        if report.deleted_endpoints:
            section += self._format_endpoint_list(report.deleted_endpoints)
        else:
            section += "_No endpoints deleted_\n\n"
        
        return section
    
    def _generate_footer(self) -> str:
        """Generate report footer"""
        if not self.add_timestamps:
            return ""
            
        footer = "## 📋 Report Information\n\n"
        footer += f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        footer += f"- **Format:** {self.output_format.title()}\n"
        if self.github_base_url:
            footer += f"- **Hyperlinks:** Enabled (Branch: {self.github_branch})\n"

        return footer
    
    def beautify(self, raw_text: str) -> str:
        """Main method to beautify the API documentation"""
        report = self.parse_raw_text(raw_text)
        
        # Build the markdown document
        markdown = f"# {self.custom_title}\n\n"
        markdown += self._generate_badges(report)
        markdown += self._generate_toc()
        markdown += self._generate_summary(report)
        markdown += self._generate_overview(report)
        markdown += self._generate_endpoints_section(report)
        markdown += self._generate_changes_section(report)
        markdown += self._generate_footer()
        
        return markdown


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Beautify API endpoint summaries into professional Markdown documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python api_beautifier.py input.txt -o output.md
  python api_beautifier.py input.txt --title "My API Docs" --no-badges
  python api_beautifier.py input.txt --github-url "https://github.com/user/repo/blob" --branch "main"
  python api_beautifier.py input.txt --format gitlab --no-toc
        """
    )
    
    # Required arguments
    parser.add_argument("input", help="Input file containing raw API summary")
    
    # Optional arguments
    parser.add_argument("-o", "--output", help="Output markdown file (default: stdout)")
    parser.add_argument("--title", default="API Endpoints Documentation", 
                       help="Custom title for the documentation")
    parser.add_argument("--format", choices=["github", "gitlab", "generic"], 
                       default="github", help="Output format")
    
    # Hyperlink options
    parser.add_argument("--github-url", 
                       help="Base GitHub URL for hyperlinks (e.g., 'https://github.com/user/repo/blob')")
    parser.add_argument("--branch", default="main",
                       help="GitHub branch name for hyperlinks (default: main)")
    
    # Feature toggles
    parser.add_argument("--no-toc", action="store_true", 
                       help="Disable table of contents")
    parser.add_argument("--no-summary", action="store_true", 
                       help="Disable executive summary")
    parser.add_argument("--no-badges", action="store_true", 
                       help="Disable status badges")
    parser.add_argument("--no-sort", action="store_true", 
                       help="Disable endpoint sorting")
    parser.add_argument("--no-timestamps", action="store_true", 
                       help="Disable timestamps in footer")
    
    # Advanced options
    parser.add_argument("--group-by-category", action="store_true", 
                       help="Group endpoints by category (experimental)")
    
    args = parser.parse_args()
    
    # Read input
    try:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file '{args.input}' not found")
            return 1
            
        raw_text = input_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading input file: {e}")
        return 1
    
    # Initialize beautifier
    beautifier = APIBeautifier(
        include_toc=not args.no_toc,
        include_summary=not args.no_summary,
        include_badges=not args.no_badges,
        sort_endpoints=not args.no_sort,
        group_by_category=args.group_by_category,
        add_timestamps=not args.no_timestamps,
        custom_title=args.title,
        output_format=args.format,
        github_base_url=args.github_url,
        github_branch=args.branch
    )
    
    # Generate markdown
    try:
        markdown = beautifier.beautify(raw_text)
    except Exception as e:
        print(f"Error processing input: {e}")
        return 1
    
    # Output result
    try:
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(markdown, encoding='utf-8')
            print(f"✅ Documentation saved to {args.output}")
        else:
            print(markdown)
    except Exception as e:
        print(f"Error writing output: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())