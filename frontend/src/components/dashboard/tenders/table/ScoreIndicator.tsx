import React from 'react';

interface ScoreIndicatorProps {
  score: number;
}

export const ScoreIndicator: React.FC<ScoreIndicatorProps> = ({ score }) => {
  const percentage = score * 100;
  let color = "bg-red-500/80";
  if (percentage >= 60) color = "bg-green-600/80";
  else if (percentage >= 45) color = "bg-yellow-500/80";
  
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${color}`} />
      <span>{percentage.toFixed(1)}%</span>
    </div>
  );
};