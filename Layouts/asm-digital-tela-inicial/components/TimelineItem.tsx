import React from 'react';
import { AutomationTask } from '../types';

interface TimelineItemProps {
  task: AutomationTask;
  isLast: boolean;
}

export const TimelineItem: React.FC<TimelineItemProps> = ({ task, isLast }) => {
  return (
    <div className={`pl-6 relative ${isLast ? '' : 'pb-8'}`}>
      {/* Dot on the line */}
      <span className={`
        absolute -left-[5px] top-1 h-2.5 w-2.5 rounded-full ring-4 ring-white shadow-sm z-10
        ${task.isNext ? 'bg-primary' : 'bg-slate-300'}
      `}></span>
      
      <div className="flex flex-col gap-1">
        {task.isNext ? (
          <span className="text-xs font-bold text-primary bg-blue-50 w-fit px-2 py-0.5 rounded-full mb-1">
            {task.time} (Em breve)
          </span>
        ) : (
          <span className="text-xs font-bold text-slate-400">
            {task.time}
          </span>
        )}
        
        <p className={`text-sm ${task.isNext ? 'font-bold text-slate-900' : 'font-semibold text-slate-800'}`}>
          {task.title}
        </p>
        <p className="text-xs text-slate-500">{task.subtitle}</p>
      </div>
    </div>
  );
};