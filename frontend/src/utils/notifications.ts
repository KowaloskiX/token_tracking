export const formatDate = (dateString: string) => {
  if (!dateString) return 'Invalid date';
  
  try {
    // Handle both ISO format and other formats
    const date = new Date(dateString);
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return 'Invalid date';
    }
    
    return date.toLocaleDateString('pl-PL', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (error) {
    console.warn('Failed to format date:', dateString, error);
    return 'Invalid date';
  }
};

// Helper function that takes translation function as parameter
export const getNotificationTypeText = (type: string, t: any) => {
  switch (type.toLowerCase()) {
    case 'success': return t('types.success');
    case 'warning': return t('types.warning');
    case 'error': return t('types.error');
    case 'info': return t('types.info');
    case 'update': return t('types.update');
    case 'results': return t('types.results');
    default: return t('types.info');
  }
};