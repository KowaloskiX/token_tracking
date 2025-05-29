import React, { useEffect } from 'react';

interface AllTendersPopupProps {
  isOpen: boolean;
  onClose: () => void;
  message: string;
}

const AllTendersPopup: React.FC<AllTendersPopupProps> = ({ isOpen, onClose, message }) => {
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        onClose();
      }, 5000);
      return () => clearTimeout(timer); 
    }
  }, [isOpen, onClose]);

  return (
    isOpen && (
      <div className="fixed bottom-4 right-4 bg-green-600/80 text-white px-4 py-2 rounded-lg shadow-md">
        <p>{message}</p>
      </div>
    )
  );
};

export default AllTendersPopup;
