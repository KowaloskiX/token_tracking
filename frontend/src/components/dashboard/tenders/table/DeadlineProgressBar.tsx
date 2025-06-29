import React from 'react';
import { calculateProgressPercentage } from '@/utils/tenderDateUtils';

interface DeadlineProgressBarProps {
  createdAt: string;
  submissionDeadline: string;
  daysRemaining: number;
}

export const DeadlineProgressBar: React.FC<DeadlineProgressBarProps> = ({
  createdAt,
  submissionDeadline,
  daysRemaining
}) => {
  const getProgressColor = () => {
    if (!submissionDeadline || submissionDeadline.includes('NaN')) {
      return "bg-gray-400";
    }
    if (daysRemaining < 0) {
      return "bg-gray-400";
    }
    if (daysRemaining <= 3) {
      return "bg-red-600 opacity-70";
    }
    if (daysRemaining <= 10) {
      return "bg-amber-600 opacity-70";
    }
    if (daysRemaining <= 21) {
      return "bg-yellow-600 opacity-70";
    }
    return "bg-green-600 opacity-70";
  };

  const getProgressWidth = () => {
    if (!submissionDeadline || submissionDeadline.includes('NaN')) {
      return "100";
    }
    return calculateProgressPercentage(createdAt, submissionDeadline);
  };

  return (
    <div className="w-full bg-secondary-hover rounded-full h-2">
      <div
        className={`h-2 rounded-full transition-all duration-200 ${getProgressColor()}`}
        style={{
          width: `${getProgressWidth()}%`
        }}
      />
    </div>
  );
};