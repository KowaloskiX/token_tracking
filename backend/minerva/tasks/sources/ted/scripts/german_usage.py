#!/usr/bin/env python3
"""
Usage script for TED German Original Link Extractor
This script demonstrates how to use the German extractor and export results
"""

import asyncio
import json
import csv
from datetime import datetime
from pathlib import Path

from minerva.tasks.sources.ted.scripts.german_link_extractor import TedGermanOriginalLinkExtractor, GermanTenderOriginalInfo

async def run_german_extraction_and_export():
    """Run the German extraction and export results to multiple formats"""
    
    extractor = TedGermanOriginalLinkExtractor()
    
    # Configuration
    inputs = {
        'max_pages': 50,  # Number of pages to scrape
        'start_date': '2025-06-01'  # Optional: only get tenders from this date onwards
    }
    
    print("Starting TED German original link extraction...")
    print(f"Max pages: {inputs['max_pages']}")
    print(f"Start date: {inputs.get('start_date', 'No date filter')}")
    print("-" * 50)
    
    # Run extraction
    results = await extractor.execute(inputs)
    
    tenders = results['tenders']
    summary = results['summary']
    
    # Print summary
    print(f"\n📊 GERMAN EXTRACTION SUMMARY")
    print(f"Total tenders processed: {summary['total_processed']}")
    print(f"Pages scraped: {summary['pages_scraped']}")
    print(f"\n📈 GERMAN SOURCE TYPE DISTRIBUTION:")
    for source_type, count in summary['source_type_distribution'].items():
        percentage = (count / summary['total_processed']) * 100
        print(f"  {source_type}: {count} ({percentage:.1f}%)")
    
    # Export to different formats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Export to JSON
    json_file = f"ted_german_original_links_{timestamp}.json"
    export_german_to_json(tenders, summary, json_file)
    print(f"\n💾 Exported to JSON: {json_file}")
    
    # 2. Export to CSV
    csv_file = f"ted_german_original_links_{timestamp}.csv"
    export_german_to_csv(tenders, csv_file)
    print(f"💾 Exported to CSV: {csv_file}")
    
    # 3. Generate analysis report
    report_file = f"ted_german_analysis_report_{timestamp}.txt"
    generate_german_analysis_report(tenders, summary, report_file)
    print(f"📄 Generated analysis report: {report_file}")
    
    # Print discovery analytics for German platforms
    discovery = results.get('discovery_analytics', {})
    if discovery:
        print(f"\n🔍 GERMAN DISCOVERY ANALYTICS:")
        print(f"Total unique German domains found: {discovery.get('total_unique_domains', 0)}")
        
        confidence = discovery.get('confidence_breakdown', {})
        print(f"\n📊 GERMAN CONFIDENCE BREAKDOWN:")
        for category, count in confidence.items():
            if count > 0:
                print(f"  {category.replace('_', ' ').title()}: {count}")
        
        german_insights = discovery.get('german_specific_insights', {})
        if german_insights:
            print(f"\n🇩🇪 GERMAN-SPECIFIC INSIGHTS:")
            print(f"  Federal platforms: {german_insights.get('federal_platforms', 0)}")
            print(f"  State platforms: {german_insights.get('state_platforms', 0)}")
            print(f"  Local platforms: {german_insights.get('local_platforms', 0)}")
            print(f"  Procurement-specific: {german_insights.get('procurement_specific', 0)}")
        
        newly_discovered = discovery.get('newly_discovered_platforms', [])
        if newly_discovered:
            print(f"\n🆕 NEWLY DISCOVERED GERMAN PLATFORMS ({len(newly_discovered)}):")
            for i, domain in enumerate(newly_discovered[:10], 1):  # Show first 10
                count = discovery.get('discovered_domains', {}).get(domain, 0)
                print(f"  {i:2d}. {domain} ({count} tenders)")
            if len(newly_discovered) > 10:
                print(f"     ... and {len(newly_discovered) - 10} more")
        
        discovered_domains = discovery.get('discovered_domains', {})
        if discovered_domains:
            print(f"\n🏆 TOP DISCOVERED GERMAN DOMAINS:")
            sorted_domains = sorted(discovered_domains.items(), key=lambda x: x[1], reverse=True)
            for i, (domain, count) in enumerate(sorted_domains[:15], 1):
                print(f"  {i:2d}. {domain:35} {count:3d} tenders")
    
    # Enhanced sample results for German tenders
    print(f"\n🔍 SAMPLE GERMAN RESULTS WITH DISCOVERY INFO (first 10):")
    print("-" * 120)
    for i, tender in enumerate(tenders[:10], 1):
        source_type = tender.original_source_type
        is_new = source_type.startswith(('procurement_platform_', 'potential_platform_', 'unknown_platform_', 'federal_gov_', 'state_gov_', 'local_gov_', 'gov_platform_'))
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

def export_german_to_json(tenders: list, summary: dict, filename: str):
    """Export German results to JSON format"""
    data = {
        'extraction_date': datetime.now().isoformat(),
        'country': 'Germany',
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

def export_german_to_csv(tenders: list, filename: str):
    """Export German results to CSV format"""
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

def generate_german_analysis_report(tenders: list, summary: dict, filename: str):
    """Generate a detailed analysis report for German tenders"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("TED GERMAN ORIGINAL LINKS ANALYSIS REPORT\n")
        f.write("=" * 55 + "\n\n")
        
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Country: Germany (DEU)\n")
        f.write(f"Total tenders analyzed: {summary['total_processed']}\n")
        f.write(f"Pages scraped: {summary['pages_scraped']}\n\n")
        
        # Source type analysis
        f.write("GERMAN SOURCE TYPE DISTRIBUTION:\n")
        f.write("-" * 35 + "\n")
        total = summary['total_processed']
        for source_type, count in sorted(summary['source_type_distribution'].items(), 
                                       key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            f.write(f"{source_type:25} {count:4d} ({percentage:5.1f}%)\n")
        
        # German platform analysis
        f.write("\nGERMAN PLATFORM ANALYSIS:\n")
        f.write("-" * 25 + "\n")
        
        german_platform_stats = {}
        for tender in tenders:
            source_type = tender.original_source_type
            if source_type != "TED E2NOTICE" and not source_type.startswith("unknown_platform"):
                german_platform_stats[source_type] = german_platform_stats.get(source_type, 0) + 1
        
        known_platforms = sum(german_platform_stats.values())
        ted_only = summary['source_type_distribution'].get('TED E2NOTICE', 0)
        unknown = total - known_platforms - ted_only
        
        f.write(f"Known German platforms: {known_platforms:4d} ({(known_platforms/total)*100:5.1f}%)\n")
        f.write(f"TED E2NOTICE only:      {ted_only:4d} ({(ted_only/total)*100:5.1f}%)\n")
        f.write(f"Unknown platforms:      {unknown:4d} ({(unknown/total)*100:5.1f}%)\n")
        
        # Breakdown of German platforms
        if german_platform_stats:
            f.write("\nGERMAN PLATFORM BREAKDOWN:\n")
            f.write("-" * 27 + "\n")
            for platform, count in sorted(german_platform_stats.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total) * 100
                f.write(f"{platform:20} {count:4d} ({percentage:5.1f}%)\n")
        
        # Section analysis
        f.write("\nWHERE LINKS WERE FOUND:\n")
        f.write("-" * 25 + "\n")
        section_stats = {}
        for tender in tenders:
            if tender.found_in_section:
                section_stats[tender.found_in_section] = section_stats.get(tender.found_in_section, 0) + 1
        
        for section, count in sorted(section_stats.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            f.write(f"{section:40} {count:4d} ({percentage:5.1f}%)\n")
        
        # Top German organizations using external platforms
        f.write("\nTOP GERMAN ORGANIZATIONS WITH EXTERNAL PLATFORMS:\n")
        f.write("-" * 50 + "\n")
        org_platforms = {}
        for tender in tenders:
            if tender.original_source_type not in ["TED E2NOTICE"] and tender.original_source_url:
                org = tender.organization[:50]  # Truncate long names
                if org not in org_platforms:
                    org_platforms[org] = set()
                org_platforms[org].add(tender.original_source_type)
        
        # Sort by number of unique platforms used
        for org, platforms in sorted(org_platforms.items(), 
                                   key=lambda x: len(x[1]), reverse=True)[:20]:
            platform_list = ", ".join(sorted(platforms))
            f.write(f"{org:50} {platform_list}\n")
        
        # Regional analysis (German states)
        f.write("\nREGIONAL PLATFORM USAGE (if detectable):\n")
        f.write("-" * 40 + "\n")
        regional_platforms = {
            'bayern': 'vergabe_bayern',
            'nrw': 'vergabe_nrw', 
            'berlin': 'berlin_vergabe',
            'hamburg': 'hamburg_vergabe',
            'brandenburg': 'vergabe_brandenburg',
            'baden-wuerttemberg': 'baden_wuerttemberg_vergabe',
            'sachsen-anhalt': 'sachsen_anhalt_vergabe',
            'thueringen': 'thueringen_vergabe',
            'schleswig-holstein': 'schleswig_holstein_vergabe',
            'niedersachsen': 'niedersachsen_vergabe',
            'hessen': 'hessen_vergabe',
            'rheinland-pfalz': 'rheinland_pfalz_vergabe',
            'saarland': 'saarland_vergabe',
            'bremen': 'bremen_vergabe',
            'mecklenburg-vorpommern': 'mv_vergabe'
        }
        
        regional_stats = {}
        for tender in tenders:
            source_type = tender.original_source_type
            for region, platform_type in regional_platforms.items():
                if platform_type == source_type:
                    regional_stats[region] = regional_stats.get(region, 0) + 1
        
        if regional_stats:
            for region, count in sorted(regional_stats.items(), key=lambda x: x[1], reverse=True):
                f.write(f"{region.title():20} {count:4d} tenders\n")
        else:
            f.write("No regional platforms detected in this sample\n")

async def analyze_specific_german_platform(platform_name: str):
    """Analyze tenders from a specific German platform"""
    print(f"\n🔍 ANALYZING GERMAN TENDERS FROM: {platform_name.upper()}")
    print("-" * 50)
    
    extractor = TedGermanOriginalLinkExtractor()
    inputs = {'max_pages': 3}
    
    results = await extractor.execute(inputs)
    platform_tenders = [t for t in results['tenders'] 
                       if t.original_source_type == platform_name]
    
    print(f"Found {len(platform_tenders)} German tenders from {platform_name}")
    
    if platform_tenders:
        print("\nSample German tenders:")
        for i, tender in enumerate(platform_tenders[:5], 1):
            print(f"{i}. {tender.tender_id}")
            print(f"   {tender.name[:80]}{'...' if len(tender.name) > 80 else ''}")
            print(f"   {tender.original_source_url}")
            print()

async def compare_polish_vs_german():
    """Compare Polish vs German tender platform distribution"""
    print("\n📊 COMPARING POLISH VS GERMAN TENDER PLATFORMS")
    print("=" * 60)
    
    # Note: This would require both extractors to be run
    # For now, just showing the structure
    
    # Run Polish extraction
    from minerva.tasks.sources.ted.scripts.original_link_extractor import TedOriginalLinkExtractor
    polish_extractor = TedOriginalLinkExtractor()
    polish_results = await polish_extractor.execute({'max_pages': 2})
    
    # Run German extraction  
    german_extractor = TedGermanOriginalLinkExtractor()
    german_results = await german_extractor.execute({'max_pages': 2})
    
    print(f"Polish tenders analyzed: {len(polish_results['tenders'])}")
    print(f"German tenders analyzed: {len(german_results['tenders'])}")
    
    print(f"\nPolish platform distribution:")
    for platform, count in polish_results['summary']['source_type_distribution'].items():
        percentage = (count / len(polish_results['tenders'])) * 100
        print(f"  {platform}: {count} ({percentage:.1f}%)")
    
    print(f"\nGerman platform distribution:")
    for platform, count in german_results['summary']['source_type_distribution'].items():
        percentage = (count / len(german_results['tenders'])) * 100
        print(f"  {platform}: {count} ({percentage:.1f}%)")

if __name__ == "__main__":
    # Run main German extraction
    asyncio.run(run_german_extraction_and_export())
    
    # Optional: Analyze specific German platforms
    # asyncio.run(analyze_specific_german_platform("vergabe24"))
    # asyncio.run(analyze_specific_german_platform("subreport"))
    
    # Optional: Compare Polish vs German
    # asyncio.run(compare_polish_vs_german())