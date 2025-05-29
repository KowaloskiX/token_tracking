const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;


export async function convertToPdf(blob: Blob, fileType: string): Promise<Blob | null> {
  try {
    // Create a FormData object
    const formData = new FormData();
    
    // Determine file extension based on file type
    let fileName;
    switch (fileType) {
      case "doc":
        fileName = "document.doc";
        break;
      case "docx":
        fileName = "document.docx";
        break;
      case "odt":
        fileName = "document.odt";
        break;
      default:
        fileName = "document";
    }
    
    formData.append('file', blob, fileName);
    
    // Send to the backend conversion endpoint
    const response = await fetch(`${serverUrl}/files/convert-to-pdf`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`${fileType.toUpperCase()}->PDF conversion error:`, errorText);
      return null;
    }
    
    // Return the converted PDF as a blob
    return await response.blob();
  } catch (error) {
    console.error(`${fileType.toUpperCase()}->PDF conversion error:`, error);
    return null;
  }
}