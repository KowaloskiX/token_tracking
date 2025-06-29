export function exportToCsv(data: any[], filename: string) {
  if (!data || data.length === 0) {
    console.warn('No data to export');
    return;
  }

  // Get all unique keys from the data
  const headers = Array.from(new Set(data.flatMap(item => Object.keys(item))));
  
  // Helper function to escape CSV values
  const escapeCSVValue = (value: any): string => {
    if (value === null || value === undefined) {
      return '';
    }
    
    let stringValue = String(value);
    
    // If the value contains comma, newline, or quote, wrap it in quotes
    if (stringValue.includes(',') || stringValue.includes('\n') || stringValue.includes('"')) {
      // Escape existing quotes by doubling them
      stringValue = stringValue.replace(/"/g, '""');
      // Wrap in quotes
      stringValue = `"${stringValue}"`;
    }
    
    return stringValue;
  };

  // Create CSV content
  const csvContent = [
    // Header row
    headers.map(header => escapeCSVValue(header)).join(','),
    // Data rows
    ...data.map(item => 
      headers.map(header => escapeCSVValue(item[header])).join(',')
    )
  ].join('\n');

  // Create and download the file
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  
  if (link.download !== undefined) {
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
}