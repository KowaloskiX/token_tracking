"use client"
import { useDashboard } from "@/hooks/useDashboard"
import { createCheckoutSession } from "@/utils/stripe"
import {
  Avatar,
  AvatarFallback,
} from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarFooter,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from "@/components/ui/sidebar"
import {
  ChevronsUpDown,
  CreditCard,
  LogIn,
  LogOut,
  Settings,
  Sparkles,
  User,
  User2,
} from "lucide-react"
import { useState, useEffect } from "react"
import { useRouter } from 'next/navigation'

interface PriceIds {
  monthly: string;
  annual: string;
  monthly_price: number;
  annual_price: number;
  currency: string;
}

const getInitials = (name?: string) => {
  if (!name) return 'U';
  return name
    .split(' ')
    .map(word => word.charAt(0))
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

const SidebarFooterComponent = () => {
  const { 
    user, 
    reset,
    setCurrentAssistant,
    setCurrentConversation,
    setUser
  } = useDashboard()
  const [isLoading, setIsLoading] = useState(false)
  const [priceIds, setPriceIds] = useState<PriceIds>()
  const router = useRouter()

  // Fetch price IDs when component mounts
  useEffect(() => {
    const fetchPriceIds = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/stripe/prices`);
        if (!response.ok) {
          throw new Error('Failed to fetch price IDs');
        }
        const data = await response.json();
        setPriceIds(data);
      } catch (error) {
        console.error('Error fetching price IDs:', error);
      }
    };
    
    fetchPriceIds();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token')
    setCurrentAssistant(null)
    setCurrentConversation(null)
    setUser(null)
    reset()
    window.location.reload()
  }

  const handleBillingPortal = async () => {
    try {
      if (!user?.subscription?.stripe_customer_id) {
        console.error('No customer ID found');
        return;
      }

      setIsLoading(true);
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_API_URL}/stripe/create-portal-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          customer_id: user.subscription.stripe_customer_id,
          return_url: `https://www.asystent.ai/dashboard/tenders/chat`
        })
      });

      if (!response.ok) {
        throw new Error('Failed to create portal session');
      }

      const { url } = await response.json();
      window.location.href = url;
    } catch (error) {
      console.error('Error opening billing portal:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubscribe = async () => {
    try {
      if (!priceIds) {
        console.error('Price IDs not loaded');
        return;
      }

      setIsLoading(true);
      const origin = window.location.origin;
      
      await createCheckoutSession(
        priceIds.monthly,
        'monthly',
        `${origin}/dashboard/tenders/chat`,
        `${origin}/dashboard/tenders/chat?canceled=true`
      );
    } catch (error) {
      console.error('Error creating checkout session:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Guest content when no user is logged in
  if (!user) {
    return (
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="h-8 w-8 rounded-lg">
                <AvatarFallback className="rounded-lg bg-muted text-muted-foreground">
                  <User className="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">
                  Gość
                </span>
                <span className="truncate text-xs text-muted-foreground">
                  Niezalogowany
                </span>
              </div>
              <LogIn className="ml-auto size-4" />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    )
  }

  const userInitials = getInitials(user.name)
  const isPaidUser = user.subscription?.plan_type === 'standard'

  return (
    <SidebarFooter>
      <SidebarMenu>
        <SidebarMenuItem>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton
                size="lg"
                className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground cursor-pointer"
                onClick={() => router.push('/dashboard/settings')}
              >
                <Avatar className="h-8 w-8 rounded-lg">
                  <AvatarFallback className="rounded-lg bg-sidebar-accent text-primary">
                    {userInitials}
                  </AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">
                    {user.name || 'Użytkownik'}
                  </span>
                  <span className="truncate text-xs">
                    {user.email || 'Brak emaila'}
                  </span>
                </div>
                <ChevronsUpDown className="ml-auto size-4" />
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
              side="bottom"
              align="end"
              sideOffset={4}
            >
              <DropdownMenuLabel className="p-0 font-normal">
                <div 
                  className="flex items-center gap-2 px-1 py-1.5 text-left text-sm cursor-pointer hover:bg-muted rounded-sm"
                  onClick={() => router.push('/dashboard/settings')}
                >
                  <Avatar className="h-8 w-8 rounded-lg">
                    <AvatarFallback className="rounded-lg bg-sidebar-accent text-primary">
                      {userInitials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-semibold">
                      {user.name || 'Użytkownik'}
                    </span>
                    <span className="truncate text-xs">
                      {user.email || 'Brak emaila'}
                    </span>
                  </div>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem onClick={() => router.push('/dashboard/settings')}>
                  <Settings className="mr-2" />
                  Ustawienia
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="mr-2" />
                Wyloguj się
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarFooter>
  )
}

export default SidebarFooterComponent