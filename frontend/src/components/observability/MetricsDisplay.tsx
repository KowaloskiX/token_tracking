import React from 'react';

interface MetricsDisplayProps {
  stats: Array<{
    label: string;
    value: string | number;
    color?: string;
  }>;
}

export function MetricsDisplay({ stats }: MetricsDisplayProps) {
  // Determine grid columns based on number of stats
  const getGridCols = (count: number) => {
    if (count === 2) return 'grid-cols-2 justify-center max-w-md mx-auto';
    if (count === 3) return 'grid-cols-3';
    if (count === 4) return 'grid-cols-2 md:grid-cols-4';
    return 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4';
  };

  return (
    <div className={`grid ${getGridCols(stats.length)} gap-4 mb-6`}>
      {stats.map((stat, index) => (
        <div key={index} className="text-center">
          <div 
            className={`text-2xl font-bold ${stat.color || 'text-primary'}`}
          >
            {stat.value}
          </div>
          <div className="text-sm text-muted-foreground">
            {stat.label}
          </div>
        </div>
      ))}
    </div>
  );
}