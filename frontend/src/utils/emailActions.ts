const serverUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL;

export type TopicValue = 
  | 'software-development'
  | 'consultations'
  | 'ai-audit'
  | 'product-question'
  | 'bug-report'
  | 'others';

export interface TopicConfig {
  value: TopicValue;
  label: string;
  emailTitle: string;
}

export const TOPICS: TopicConfig[] = [
  { 
    value: 'software-development', 
    label: 'Rozwój rozwiązania AI',
    emailTitle: 'Zapytanie o rozwój rozwiązania AI'
  },
  { 
    value: 'consultations', 
    label: 'Warsztaty AI',
    emailTitle: 'Zapytanie o warsztaty AI'
  },
  { 
    value: 'ai-audit', 
    label: 'Audyt AI',
    emailTitle: 'Zapytanie o audyt AI'
  },
  { 
    value: 'product-question', 
    label: 'Pytanie o produkt',
    emailTitle: 'Pytanie dotyczące produktu'
  },
  { 
    value: 'bug-report', 
    label: 'Zgłoszenie problemu',
    emailTitle: 'Zgłoszenie problemu technicznego'
  },
  { 
    value: 'others', 
    label: 'Inne',
    emailTitle: 'Zapytanie ogólne'
  }
];

interface ContactFormData {
  email: string;
  phoneNumber?: string;
  topic: TopicValue;
  message: string;
}

export const sendContactFormEmail = async (formData: ContactFormData) => {

  const selectedTopic = TOPICS.find(t => t.value === formData.topic);
  if (!selectedTopic) {
    console.error('Topic not found:', formData.topic);
    throw new Error('Invalid topic');
  }

  const htmlContent = `
    <!DOCTYPE html>
    <html>
      <head>
        <style>
          body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
          }
          .header {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
          }
          .topic {
            color: #0066cc;
            font-weight: 600;
          }
          .email {
            color: #666;
            margin-bottom: 20px;
          }
          .message {
            background-color: #ffffff;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            margin-top: 20px;
          }
          .footer {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            font-size: 0.875rem;
            color: #666;
          }
        </style>
      </head>
      <body>
        <div class="header">
          <h2>Nowa wiadomość kontaktowa</h2>
          <p class="topic">Temat: ${selectedTopic?.label}</p>
          <p class="email">Od: ${formData.email}</p>
        </div>
        
        <div class="message">
          ${formData.message.replace(/\n/g, '<br>')}
        </div>
        
        <div class="footer">
          <p>Wiadomość wysłana przez formularz kontaktowy Asystent AI</p>
        </div>
      </body>
    </html>
  `;

  try {
    const url = `${serverUrl}/send-email`;
    const payload = {
      to: 'hello@asystent.ai',
      subject: `${selectedTopic?.emailTitle}`,
      html: htmlContent
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const errorData = await response.text();
      console.error('Error response:', errorData);
      throw new Error(`Failed to send email: ${response.status} ${errorData}`);
    }

    const data = await response.json();
    console.log('Success response:', data);
    return data;
  } catch (error) {
    console.error('Error in sendContactFormEmail:', error);
    throw error;
  }
};