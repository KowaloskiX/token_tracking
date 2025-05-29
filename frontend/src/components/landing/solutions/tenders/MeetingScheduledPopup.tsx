import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CalendarCheck, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const MeetingScheduledPopup = ({ onClose }: any) => {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0, y: 10 }}
          animate={{ 
            scale: 1, 
            opacity: 1, 
            y: 0,
            transition: {
              type: "spring",
              duration: 0.5,
              bounce: 0.3
            }
          }}
          exit={{ scale: 0.95, opacity: 0, y: 10 }}
        >
          <Card className="w-full max-w-lg shadow-lg p-2">
            <CardHeader className="relative">
              <Button 
                variant="ghost" 
                className="absolute right-2 top-2 h-8 w-8 p-0"
                onClick={onClose}
              >
                <X className="h-4 w-4" />
              </Button>
              <div className="flex flex-col items-center space-y-4 pt-4">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ 
                    scale: 1,
                    transition: {
                      delay: 0.2,
                      type: "spring",
                      duration: 0.7,
                      bounce: 0.4
                    }
                  }}
                  className="rounded-full bg-green-500 bg-opacity-20 p-3"
                >
                  <CalendarCheck className="h-6 w-6 text-green-700" />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ 
                    opacity: 1, 
                    y: 0,
                    transition: { delay: 0.3 }
                  }}
                >
                  <CardTitle className="text-xl text-center">
                    Do zobaczenia niebawem!
                  </CardTitle>
                </motion.div>
              </div>
            </CardHeader>
            <CardContent className="text-center pb-6">
              <motion.p
                initial={{ opacity: 0, y: 5 }}
                animate={{ 
                  opacity: 1, 
                  y: 0,
                  transition: { delay: 0.4 }
                }}
                className="text-muted-foreground mb-6"
              >
                Szczegóły spotkania zostały wysłane na Twój adres email. 
                Link do spotkania będzie dostępny w kalendarzu.
              </motion.p>
              <motion.div
                initial={{ opacity: 0, y: 5 }}
                animate={{ 
                  opacity: 1, 
                  y: 0,
                  transition: { delay: 0.5 }
                }}
                whileTap={{ scale: 0.97 }}
              >
                <Button 
                  className="text-white px-10"
                  onClick={onClose}
                >
                  Zamknij
                </Button>
              </motion.div>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default MeetingScheduledPopup;