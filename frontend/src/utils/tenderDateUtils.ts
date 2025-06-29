// utils/tenderDateUtils.ts

export const formatDate = (dateStr: string): string => {
  if (!dateStr || dateStr.includes('NaN')) return '-';

  let date: Date;
  if (dateStr.includes('-')) {
    const isoStr = dateStr.includes(' ') ? dateStr.replace(' ', 'T') : dateStr;
    date = new Date(isoStr);
  } else if (dateStr.includes('.')) {
    const [day, month, year] = dateStr.split('.').map(Number);
    date = new Date(year, month - 1, day);
  } else if (dateStr.includes('/')) {
    const cleanDateStr = dateStr.replace(/\([^)]*\)/g, '').trim();
    date = new Date(cleanDateStr);

    if (isNaN(date.getTime())) {
      const parts = cleanDateStr.split('/');
      if (parts.length === 3) {
        let day, month, year;
        if (parseInt(parts[0]) > 12) {
          day = parseInt(parts[0]);
          month = parseInt(parts[1]);
          year = parseInt(parts[2].split(' ')[0]);
        } else {
          month = parseInt(parts[0]);
          day = parseInt(parts[1]);
          year = parseInt(parts[2].split(' ')[0]);
        }
        date = new Date(year, month - 1, day);
      } else {
        return '-';
      }
    }
  } else {
    return '-';
  }

  if (isNaN(date.getTime())) return '-';
  const d = String(date.getDate()).padStart(2, '0');
  const m = String(date.getMonth() + 1).padStart(2, '0');
  return `${d}.${m}`;
};

export const extractHour = (dateStr: string): string => {
  if (!dateStr || dateStr.includes('NaN')) return '-';

  let date: Date;
  if (dateStr.includes('-')) {
    const isoStr = dateStr.includes(' ') ? dateStr.replace(' ', 'T') : dateStr;
    date = new Date(isoStr);
  } else if (dateStr.includes('/')) {
    const cleanDateStr = dateStr.replace(/\([^)]*\)/g, '').trim();
    date = new Date(cleanDateStr);
    
    if (isNaN(date.getTime())) {
      const parts = cleanDateStr.split('/');
      if (parts.length === 3) {
        const timePart = parts[2].includes(' ') ? parts[2].split(' ')[1] : null;
        if (timePart) {
          let day, month, year;
          if (parseInt(parts[0]) > 12) {
            day = parseInt(parts[0]);
            month = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]);
          } else {
            month = parseInt(parts[0]);
            day = parseInt(parts[1]);
            year = parseInt(parts[2].split(' ')[0]);
          }
          
          const [hour, minute] = timePart.split(':').map(Number);
          date = new Date(year, month - 1, day, hour, minute);
        } else {
          return '-';
        }
      } else {
        return '-';
      }
    }
  } else {
    return '-';
  }

  if (isNaN(date.getTime())) return '-';
  
  if (date.getHours() === 0 && date.getMinutes() === 0) {
    if (!dateStr.includes(':') && !dateStr.includes('T')) {
      return '-';
    }
  }
  
  const h = String(date.getHours()).padStart(2, '0');
  const m = String(date.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
};

export const formatDateTime = (dateTimeStr: string): string => {
  const date = new Date(dateTimeStr);
  return date.toLocaleString('pl-PL', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const calculateProgressPercentage = (createdAt: string, deadlineStr: string): number => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const created = new Date(createdAt);
  created.setHours(0, 0, 0, 0);

  let deadline;
  if (deadlineStr.includes('-')) {
    const isoStr = deadlineStr.includes(' ') ? deadlineStr.replace(' ', 'T') : deadlineStr;
    deadline = new Date(isoStr);
  } else if (deadlineStr.includes('.')) {
    const parts = deadlineStr.split('.');
    deadline = new Date(
      parseInt(parts[2]),
      parseInt(parts[1]) - 1,
      parseInt(parts[0])
    );
  } else if (deadlineStr.includes('/')) {
    const cleanDeadlineStr = deadlineStr.replace(/\([^)]*\)/g, '').trim();
    deadline = new Date(cleanDeadlineStr);

    if (isNaN(deadline.getTime())) {
      const parts = cleanDeadlineStr.split('/');
      if (parts.length === 3) {
        let day, month, year;
        if (parseInt(parts[0]) > 12) {
          day = parseInt(parts[0]);
          month = parseInt(parts[1]);
          year = parseInt(parts[2].split(' ')[0]);
        } else {
          month = parseInt(parts[0]);
          day = parseInt(parts[1]);
          year = parseInt(parts[2].split(' ')[0]);
        }
        deadline = new Date(year, month - 1, day);
      } else {
        return 100;
      }
    }
  } else {
    return 100;
  }

  if (isNaN(deadline.getTime())) {
    return 100;
  }

  deadline.setHours(0, 0, 0, 0);

  const totalDuration = deadline.getTime() - created.getTime();
  const elapsedDuration = today.getTime() - created.getTime();

  if (totalDuration <= 0) return 100;
  if (elapsedDuration <= 0) return 0;

  const progress = (elapsedDuration / totalDuration) * 100;
  return Math.min(100, Math.max(0, progress));
};

export const truncateText = (text: string, maxLength: number): string => {
  return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
};