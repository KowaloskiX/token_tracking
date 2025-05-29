"use client"

import React from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';
import { useParams } from 'next/navigation';
import { TOPICS, TopicValue, sendContactFormEmail } from '@/utils/emailActions';
import { useToast } from '@/hooks/use-toast';
import { Toaster } from '@/components/Toaster';

const ContactPage = () => {
    const { toast } = useToast();
    const params = useParams();
    const reasonParam = params.reason as string;
    const defaultTopic = reasonParam && TOPICS.some(t => t.value === reasonParam) 
      ? reasonParam 
      : TOPICS[0].value;
  
    const [selectedTopic, setSelectedTopic] = React.useState<TopicValue>(defaultTopic as TopicValue);
    const [email, setEmail] = React.useState('');
    const [phoneNumber, setPhoneNumber] = React.useState('');
    const [message, setMessage] = React.useState('');
    const [isSubmitting, setIsSubmitting] = React.useState(false);
  
    React.useEffect(() => {
      if (reasonParam && TOPICS.some(t => t.value === reasonParam)) {
        setSelectedTopic(reasonParam as TopicValue);
      }
    }, [reasonParam]);
  
    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        
        if (isSubmitting) {
          console.log('Already submitting, preventing duplicate submission');
          return;
        }
        
        setIsSubmitting(true);
      
        try {
          await sendContactFormEmail({
            email,
            phoneNumber,
            topic: selectedTopic,
            message
          });
          
          
          setEmail('');
          setPhoneNumber('');
          setMessage('');
          
          toast({
            title: "Poszło!",
            description: "Twoja wiadomość została wysłana. Odpowiemy najszybciej jak to tylko możliwe :)",
          });
          
        } catch (error) {
          console.error('Error in handleSubmit:', error);
          
          toast({
            title: "Wystąpił błąd",
            description: "Nie udało się wysłać wiadomości. Spróbuj ponownie później.",
            variant: "destructive",
          });
        } finally {
          setIsSubmitting(false);
        }
      };


  return (
    <div className="min-h-screen">
      <Navbar />
      <div className="container mx-auto px-4 min-h-screen flex items-center justify-center">
        <div className="grid lg:grid-cols-2 gap-8 items-center mx-auto w-full">
          {/* Form Section */}
          <div className="w-full lg:p-10 lg:py-10 mt-[6rem] lg:mt-0">
            <div className='pb-6 border-b border-b-secondary-border'>
              <h1 className="lg:text-4xl text-3xl text-foreground">Skontaktuj się z nami</h1>
              <p className='mt-2 lg:text-lg text-body-text'>Wyślij nam wiadomość, a nasz zespół zajmie się resztą.</p>
            </div>
            <div>
              <form onSubmit={handleSubmit} className="space-y-6 mt-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="mail@example.com"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phoneNumber">Numer telefonu (opcjonalne)</Label>
                  <Input
                    id="phoneNumber"
                    type="tel"
                    placeholder="+48 123 456 789"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="w-full"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Temat</Label>
                  {/* Mobile: Select dropdown */}
                  <div className="lg:hidden">
                    <Select 
                      value={selectedTopic} 
                      onValueChange={(value) => setSelectedTopic(value as TopicValue)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Wybierz temat" />
                      </SelectTrigger>
                      <SelectContent>
                        {TOPICS.map((topic) => (
                          <SelectItem key={topic.value} value={topic.value}>
                            {topic.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  {/* Desktop: Radio group */}
                  <div className="hidden lg:block">
                    <RadioGroup 
                      value={selectedTopic} 
                      onValueChange={(value) => setSelectedTopic(value as TopicValue)}
                      className="flex flex-wrap gap-4 items-center"
                    >
                      {TOPICS.map((topic) => (
                        <div key={topic.value} className="flex items-center space-x-2">
                          <RadioGroupItem value={topic.value} id={topic.value} />
                          <Label htmlFor={topic.value} className="cursor-pointer">
                            {topic.label}
                          </Label>
                        </div>
                      ))}
                    </RadioGroup>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="message">Wiadomość (opcjonalne)</Label>
                  <Textarea
                    id="message"
                    placeholder="Kochany zespole Asystenta AI..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    className="min-h-[150px]"
                  />
                </div>

                <Button 
                    type="submit" 
                    disabled={isSubmitting} 
                    className="w-full"
                    >
                    {isSubmitting ? 'Wysyłanie...' : 'Wyślij wiadomość'}
                </Button>
              </form>
            </div>
          </div>
            {/* Image Section */}
          <div className="hidden lg:block h-full pt-8">
            <div className="relative h-full w-full rounded-xl overflow-hidden">
              <img 
                src="/images/aesthetic_office_2.png"
                alt="Contact us"
                className="object-cover w-full h-full"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
              <div className="absolute bottom-0 left-0 p-8 text-white">
                <h2 className="text-3xl mb-2">Bądźmy w kontakcie.</h2>
                <p className="text-lg opacity-90">Nasz zespół czyta i odpowiada na każdą wiadomość.</p>
              </div>
            </div>
          </div>

        </div>
      </div>
      <Footer />
      <Toaster />
    </div>
  );
};

export default ContactPage;