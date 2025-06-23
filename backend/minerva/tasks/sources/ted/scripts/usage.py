#!/usr/bin/env python3
"""
Usage script for TED Original Link Extractor
This script demonstrates how to use the extractor and export results
"""

import asyncio
import json
import csv
from datetime import datetime
from pathlib import Path

from minerva.tasks.sources.ted.scripts.original_link_extractor import TedOriginalLinkExtractor, TenderOriginalInfo

async def run_extraction_and_export():
    """Run the extraction and export results to multiple formats"""
    
    extractor = TedOriginalLinkExtractor()
    
    # Configuration
    inputs = {
        'max_pages': 50,  # Number of pages to scrape
        'start_date': '2025-06-01'  # Optional: only get tenders from this date onwards
    }
    
    print("Starting TED original link extraction...")
    print(f"Max pages: {inputs['max_pages']}")
    print(f"Start date: {inputs.get('start_date', 'No date filter')}")
    print("-" * 50)
    
    # Run extraction
    results = await extractor.execute(inputs)
    
    tenders = results['tenders']
    summary = results['summary']
    
    # Print summary
    print(f"\n📊 EXTRACTION SUMMARY")
    print(f"Total tenders processed: {summary['total_processed']}")
    print(f"Pages scraped: {summary['pages_scraped']}")
    print(f"\n📈 SOURCE TYPE DISTRIBUTION:")
    for source_type, count in summary['source_type_distribution'].items():
        percentage = (count / summary['total_processed']) * 100
        print(f"  {source_type}: {count} ({percentage:.1f}%)")
    
    # Export to different formats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Export to JSON
    json_file = f"ted_original_links_{timestamp}.json"
    export_to_json(tenders, summary, json_file)
    print(f"\n💾 Exported to JSON: {json_file}")
    
    # 2. Export to CSV
    csv_file = f"ted_original_links_{timestamp}.csv"
    export_to_csv(tenders, csv_file)
    print(f"💾 Exported to CSV: {csv_file}")
    
    # 3. Generate analysis report
    report_file = f"ted_analysis_report_{timestamp}.txt"
    generate_analysis_report(tenders, summary, report_file)
    print(f"📄 Generated analysis report: {report_file}")
    
    # Print discovery analytics
    discovery = results.get('discovery_analytics', {})
    if discovery:
        print(f"\n🔍 DISCOVERY ANALYTICS:")
        print(f"Total unique domains found: {discovery.get('total_unique_domains', 0)}")
        
        confidence = discovery.get('confidence_breakdown', {})
        print(f"\n📊 CONFIDENCE BREAKDOWN:")
        for category, count in confidence.items():
            if count > 0:
                print(f"  {category.replace('_', ' ').title()}: {count}")
        
        newly_discovered = discovery.get('newly_discovered_platforms', [])
        if newly_discovered:
            print(f"\n🆕 NEWLY DISCOVERED PLATFORMS ({len(newly_discovered)}):")
            for i, domain in enumerate(newly_discovered[:10], 1):  # Show first 10
                count = discovery.get('discovered_domains', {}).get(domain, 0)
                print(f"  {i:2d}. {domain} ({count} tenders)")
            if len(newly_discovered) > 10:
                print(f"     ... and {len(newly_discovered) - 10} more")
        
        discovered_domains = discovery.get('discovered_domains', {})
        if discovered_domains:
            print(f"\n🏆 TOP DISCOVERED DOMAINS:")
            sorted_domains = sorted(discovered_domains.items(), key=lambda x: x[1], reverse=True)
            for i, (domain, count) in enumerate(sorted_domains[:15], 1):
                print(f"  {i:2d}. {domain:30} {count:3d} tenders")
    
    # Enhanced sample results
    print(f"\n🔍 SAMPLE RESULTS WITH DISCOVERY INFO (first 10):")
    print("-" * 120)
    for i, tender in enumerate(tenders[:10], 1):
        source_type = tender.original_source_type
        is_new = source_type.startswith(('procurement_platform_', 'potential_platform_', 'unknown_platform_', 'gov_platform_', 'local_gov_'))
        discovery_flag = " 🆕" if is_new else ""
        
        print(f"{i:2d}. {tender.tender_id} | {source_type}{discovery_flag}")
        print(f"    Name: {tender.name[:80]}{'...' if len(tender.name) > 80 else ''}")
        print(f"    Org:  {tender.organization[:60]}{'...' if len(tender.organization) > 60 else ''}")
        if tender.original_source_url:
            print(f"    URL:  {tender.original_source_url}")
            print(f"    Found in: {tender.found_in_section}")
        else:
            print(f"    URL:  No original link found (TED E2NOTICE)")
        print()

def export_to_json(tenders: list, summary: dict, filename: str):
    """Export results to JSON format"""
    data = {
        'extraction_date': datetime.now().isoformat(),
        'summary': summary,
        'tenders': []
    }
    
    for tender in tenders:
        tender_dict = {
            'tender_id': tender.tender_id,
            'name': tender.name,
            'organization': tender.organization,
            'location': tender.location,
            'submission_deadline': tender.submission_deadline,
            'initiation_date': tender.initiation_date,
            'details_url': tender.details_url,
            'original_source_url': tender.original_source_url,
            'original_source_type': tender.original_source_type,
            'found_in_section': tender.found_in_section
        }
        data['tenders'].append(tender_dict)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def export_to_csv(tenders: list, filename: str):
    """Export results to CSV format"""
    fieldnames = [
        'tender_id', 'name', 'organization', 'location', 
        'submission_deadline', 'initiation_date', 'details_url',
        'original_source_url', 'original_source_type', 'found_in_section'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for tender in tenders:
            writer.writerow({
                'tender_id': tender.tender_id,
                'name': tender.name,
                'organization': tender.organization,
                'location': tender.location,
                'submission_deadline': tender.submission_deadline,
                'initiation_date': tender.initiation_date,
                'details_url': tender.details_url,
                'original_source_url': tender.original_source_url or '',
                'original_source_type': tender.original_source_type,
                'found_in_section': tender.found_in_section or ''
            })

def generate_analysis_report(tenders: list, summary: dict, filename: str):
    """Generate a detailed analysis report with discovery insights"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("TED ORIGINAL LINKS ANALYSIS REPORT\n")
        f.write("=" * 50 + "\n\n")
        
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total tenders analyzed: {summary['total_processed']}\n")
        f.write(f"Pages scraped: {summary['pages_scraped']}\n\n")
        
        # Source type analysis
        f.write("SOURCE TYPE DISTRIBUTION:\n")
        f.write("-" * 30 + "\n")
        total = summary['total_processed']
        for source_type, count in sorted(summary['source_type_distribution'].items(), 
                                       key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            f.write(f"{source_type:30} {count:4d} ({percentage:5.1f}%)\n")
        
        # Discovery analytics section
        f.write("\nDISCOVERY ANALYTICS:\n")
        f.write("-" * 20 + "\n")
        
        # Categorize discovered platforms
        known_count = 0
        discovery_categories = {
            'procurement_platforms': 0,
            'potential_platforms': 0,
            'gov_platforms': 0,
            'local_gov': 0,
            'unknown_platforms': 0
        }
        
        for source_type, count in summary['source_type_distribution'].items():
            if source_type == "TED E2NOTICE":
                continue
            elif not source_type.startswith(('procurement_platform_', 'potential_platform_', 'unknown_platform_', 'gov_platform_', 'local_gov_')):
                known_count += count
            else:
                for category in discovery_categories.keys():
                    if source_type.startswith(f"{category}_"):
                        discovery_categories[category] += count
                        break
        
        ted_only = summary['source_type_distribution'].get('TED E2NOTICE', 0)
        total_discovered = sum(discovery_categories.values())
        
        f.write(f"Known platforms:           {known_count:4d} ({(known_count/total)*100:5.1f}%)\n")
        f.write(f"Newly discovered:          {total_discovered:4d} ({(total_discovered/total)*100:5.1f}%)\n")
        f.write(f"  - Procurement platforms: {discovery_categories['procurement_platforms']:4d}\n")
        f.write(f"  - Potential platforms:   {discovery_categories['potential_platforms']:4d}\n")
        f.write(f"  - Government platforms:  {discovery_categories['gov_platforms']:4d}\n")
        f.write(f"  - Local government:      {discovery_categories['local_gov']:4d}\n")
        f.write(f"  - Unknown platforms:     {discovery_categories['unknown_platforms']:4d}\n")
        f.write(f"TED E2NOTICE only:         {ted_only:4d} ({(ted_only/total)*100:5.1f}%)\n")
        
        # List newly discovered platforms
        f.write("\nNEWLY DISCOVERED PLATFORMS:\n")
        f.write("-" * 30 + "\n")
        discovered_platforms = {}
        for tender in tenders:
            source_type = tender.original_source_type
            if source_type.startswith(('procurement_platform_', 'potential_platform_', 'unknown_platform_', 'gov_platform_', 'local_gov_')):
                if '_' in source_type:
                    domain = source_type.split('_', 2)[-1] if source_type.count('_') > 1 else source_type.split('_', 1)[-1]
                    category = source_type.split('_')[0] + '_' + source_type.split('_')[1]
                    if domain not in discovered_platforms:
                        discovered_platforms[domain] = {'count': 0, 'category': category, 'urls': set()}
                    discovered_platforms[domain]['count'] += 1
                    if tender.original_source_url:
                        discovered_platforms[domain]['urls'].add(tender.original_source_url)
        
        # Sort by count and display
        for domain, info in sorted(discovered_platforms.items(), key=lambda x: x[1]['count'], reverse=True)[:25]:
            f.write(f"{domain:40} {info['count']:3d} tenders ({info['category']})\n")
            if info['urls']:
                sample_url = list(info['urls'])[0]
                f.write(f"    Sample URL: {sample_url}\n")
        
        # Section analysis
        f.write("\nWHERE LINKS WERE FOUND:\n")
        f.write("-" * 25 + "\n")
        section_stats = {}
        for tender in tenders:
            if tender.found_in_section:
                section_stats[tender.found_in_section] = section_stats.get(tender.found_in_section, 0) + 1
        
        for section, count in sorted(section_stats.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            f.write(f"{section:30} {count:4d} ({percentage:5.1f}%)\n")
        
        # Top organizations with external platforms
        f.write("\nTOP ORGANIZATIONS WITH EXTERNAL PLATFORMS:\n")
        f.write("-" * 45 + "\n")
        org_platforms = {}
        for tender in tenders:
            if tender.original_source_type not in ["TED E2NOTICE"] and tender.original_source_url:
                org = tender.organization[:50]  # Truncate long names
                if org not in org_platforms:
                    org_platforms[org] = set()
                org_platforms[org].add(tender.original_source_type.split('_')[0] if '_' in tender.original_source_type else tender.original_source_type)
        
        # Sort by number of unique platform types used
        for org, platforms in sorted(org_platforms.items(), 
                                   key=lambda x: len(x[1]), reverse=True)[:20]:
            platform_list = ", ".join(sorted(platforms))
            f.write(f"{org:50} {platform_list}\n")

async def analyze_specific_platform(platform_name: str):
    """Analyze tenders from a specific platform"""
    print(f"\n🔍 ANALYZING TENDERS FROM: {platform_name.upper()}")
    print("-" * 50)
    
    extractor = TedOriginalLinkExtractor()
    inputs = {'max_pages': 50}
    
    results = await extractor.execute(inputs)
    platform_tenders = [t for t in results['tenders'] 
                       if t.original_source_type == platform_name]
    
    print(f"Found {len(platform_tenders)} tenders from {platform_name}")
    
    if platform_tenders:
        print("\nSample tenders:")
        for i, tender in enumerate(platform_tenders[:5], 1):
            print(f"{i}. {tender.tender_id}")
            print(f"   {tender.name[:80]}{'...' if len(tender.name) > 80 else ''}")
            print(f"   {tender.original_source_url}")
            print()

if __name__ == "__main__":
    # Run main extraction
    asyncio.run(run_extraction_and_export())
    
    # Optional: Analyze specific platforms
    # asyncio.run(analyze_specific_platform("eb2b"))
    # asyncio.run(analyze_specific_platform("platformazakupowa"))