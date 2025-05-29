import { read, utils } from 'xlsx';

export interface ExcelFileStats {
  filename: string;
  isLargeDataset: boolean;
}

interface ExcelRow {
  [key: string]: unknown;
}

export const analyzeExcelFile = async (file: File): Promise<ExcelFileStats> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target?.result as ArrayBuffer);
        const workbook = read(data, { type: 'array' });
        
        let totalRows = 0;
        let maxColumns = 0;

        for (const sheetName of workbook.SheetNames) {
          const worksheet = workbook.Sheets[sheetName];
          const jsonData = utils.sheet_to_json(worksheet) as ExcelRow[];
          
          totalRows += jsonData.length;
          
          // Check columns in each row
          jsonData.forEach((row: ExcelRow) => {
            const columnCount = Object.keys(row).length;
            maxColumns = Math.max(maxColumns, columnCount);
          });

          // If we already know it's a large dataset, we can break early
          if (totalRows > 150 || maxColumns > 150) {
            break;
          }
        }

        resolve({
          filename: file.name,
          isLargeDataset: totalRows > 150 || maxColumns > 150
        });
      } catch (error) {
        reject(error);
      }
    };

    reader.onerror = () => {
      reject(new Error('Failed to read file'));
    };

    reader.readAsArrayBuffer(file);
  });
};
