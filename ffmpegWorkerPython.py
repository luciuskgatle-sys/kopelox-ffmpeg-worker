import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { base44 } from "@/api/base44Client";
import { createPageUrl } from "./utils";
import { Button } from "@/components/ui/button";
import { 
                  Menu, X, Home, Video, BarChart3, Settings, LogOut, Users, 
                  Flag, Shield, ChevronDown, User as UserIcon, Bell, Trophy, Search, Music
                } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";

export default function Layout({ children, currentPageName }) {
  const [user, setUser] = useState(null);
      const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
      const [loading, setLoading] = useState(true);
      const [theme, setTheme] = useState(localStorage.getItem('kopeloTheme') || 'patriotic');
      const [unreadNotifications, setUnreadNotifications] = useState(0);
  const navigate = useNavigate();

  const handleThemeChange = (newTheme) => {
    setTheme(newTheme);
    localStorage.setItem('kopeloTheme', newTheme);
  };

  useEffect(() => {
    const loadUser = async () => {
      try {
        const isAuth = await base44.auth.isAuthenticated();
        if (isAuth) {
          const userData = await base44.auth.me();
          setUser(userData);

          // Load notifications with timeout
          try {
            Promise.race([
              base44.entities.Notification.filter({
                recipient_email: userData.email,
                is_read: false
              }),
              new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 2000))
            ]).then(notifications => {
              setUnreadNotifications(notifications.length);
            }).catch(() => {
              // Timeout or error - skip notifications
            });
          } catch (notifError) {
            // Notifications entity may not be accessible
          }
        }
      } catch (e) {
        console.log("Not authenticated");
      } finally {
        setLoading(false);
      }
    };
    loadUser();

    // Set Open Graph meta tags
    const metaTags = [
      { property: 'og:title', content: 'KopeloX - A Collective Culture Platform' },
      { property: 'og:description', content: 'Mobilising people through shared cultural expressions. No DNA. Just RSA.' },
      { property: 'og:image', content: '/kopelox-logo-social.png' },
      { property: 'og:type', content: 'website' },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: 'KopeloX - A Collective Culture Platform' },
      { name: 'twitter:description', content: 'Mobilising people through shared cultural expressions. No DNA. Just RSA.' },
      { name: 'twitter:image', content: '/kopelox-logo-social.png' }
    ];

    metaTags.forEach(tag => {
      const key = tag.property || tag.name;
      const attr = tag.property ? 'property' : 'name';
      let element = document.querySelector(`meta[${attr}="${key}"]`);
      if (!element) {
        element = document.createElement('meta');
        element.setAttribute(attr, key);
        document.head.appendChild(element);
      }
      element.setAttribute('content', tag.content);
    });
  }, []);

  const handleLogout = () => {
    base44.auth.logout();
  };

  const isAdmin = user?.role === "admin";

  const publicPages = [
    { name: "Home", icon: Home, page: "Home" },
    { name: "Global Choir", icon: Music, page: "ChoirView" },
    { name: "Community", icon: Users, page: "CommunityFeed" },
    { name: "Leaderboard", icon: Trophy, page: "Leaderboard" },
  ];

  const followingPages = [
    { name: "Following", icon: Users, page: "FollowingFeed" },
  ];

  const userPages = [
    { name: "Participate", icon: Video, page: "Participate" },
    { name: "My Contributions", icon: Flag, page: "MyContributions" },
  ];

  const adminPages = [
    { name: "Dashboard", icon: BarChart3, page: "AdminDashboard" },
    { name: "AI Sync", icon: Video, page: "AdminAISync" },
    { name: "Guide Track", icon: Music, page: "UploadMasterGuide" },
    { name: "Moderation", icon: Shield, page: "Moderation" },
    { name: "Campaigns", icon: Settings, page: "ManageCampaigns" },
    { name: "Bafana Fridays", icon: Flag, page: "ManageBafanaFridays" },
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-900 via-yellow-600 to-red-700 flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-white border-t-transparent rounded-full animate-spin" />
      </div>
    );
    }

    const themes = {
    patriotic: {
      name: "Patriotic SA",
      gradient: "from-[#007A4D] via-[#FFB81C] to-[#DE3831]",
      primary: "#007A4D",
      secondary: "#FFB81C",
      accent: "#DE3831",
      logo: "Kopelo",
      logoAccent: "X",
      logoStyle: "font-black tracking-tighter",
      headerBg: "bg-gradient-to-r from-[#DE3831] via-[#FFB81C] to-[#007A4D]",
      buttonStyle: "bg-[#007A4D] hover:bg-[#006641]"
    },
    digital: {
      name: "Digital Unity",
      gradient: "from-purple-600 via-blue-500 to-cyan-400",
      primary: "#7C3AED",
      secondary: "#3B82F6",
      accent: "#06B6D4",
      logo: "KOPELO",
      logoAccent: "X",
      logoStyle: "font-black tracking-wider",
      headerBg: "bg-gradient-to-r from-purple-600 via-blue-500 to-cyan-400",
      buttonStyle: "bg-purple-600 hover:bg-purple-700"
    },
    community: {
      name: "Community Warmth",
      gradient: "from-orange-500 via-rose-400 to-pink-500",
      primary: "#F97316",
      secondary: "#FB7185",
      accent: "#EC4899",
      logo: "kopelo",
      logoAccent: "X",
      logoStyle: "font-bold tracking-tight",
      headerBg: "bg-gradient-to-r from-orange-500 via-rose-400 to-pink-500",
      buttonStyle: "bg-orange-500 hover:bg-orange-600"
    }
    };

    const currentTheme = themes[theme];

    return (
    <div className="bg-slate-50">
      <style>{`
        :root {
          --theme-primary: ${currentTheme.primary};
          --theme-secondary: ${currentTheme.secondary};
          --theme-accent: ${currentTheme.accent};
        }
      `}</style>

      {/* Header */}
      <header className="sticky top-0 z-50 bg-slate-900 border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-3">
          <div className="flex items-center justify-between h-20">
            {/* Logo */}
            <Link to={createPageUrl("Home")} className="flex items-center">
              <img 
                src="https://qtrypzzcjebvfcihiynt.supabase.co/storage/v1/object/public/base44-prod/public/695eade926c226387ff83d9d/7c3eae2f4_ChatGPTImageJan24202605_34_40AM.png" 
                alt="KopeloX" 
                className="h-32 w-auto"
              />
            </Link>

            {/* Desktop Navigation */}
            <TooltipProvider delayDuration={100}>
            <nav className="hidden md:flex items-center gap-6 flex-1 justify-center">
              {publicPages.map((item) => (
                <Tooltip key={item.page}>
                  <TooltipTrigger asChild>
                    <Link
                      to={createPageUrl(item.page)}
                      className="flex items-center gap-1 text-white/80 hover:text-white transition-colors text-xs"
                    >
                      <item.icon className="w-5 h-5" />
                      <span className="font-medium hidden lg:inline">{item.name}</span>
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>{item.name}</TooltipContent>
                </Tooltip>
              ))}

              {user && userPages.map((item) => (
                <Tooltip key={item.page}>
                  <TooltipTrigger asChild>
                    <Link
                      to={createPageUrl(item.page)}
                      className="flex items-center gap-1 text-white/80 hover:text-white transition-colors text-xs"
                    >
                      <item.icon className="w-5 h-5" />
                      <span className="font-medium hidden lg:inline">{item.name}</span>
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>{item.name}</TooltipContent>
                </Tooltip>
              ))}

              {user && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Link
                      to={createPageUrl("Notifications")}
                      className="relative flex items-center text-white/80 hover:text-white transition-colors p-1"
                    >
                      <Bell className="w-5 h-5" />
                      {unreadNotifications > 0 && (
                        <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white rounded-full w-3 h-3 flex items-center justify-center font-bold text-[8px]">
                          {unreadNotifications}
                        </span>
                      )}
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>Notifications</TooltipContent>
                </Tooltip>
              )}

              {isAdmin && (
                <DropdownMenu>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <DropdownMenuTrigger asChild>
                        <button className="flex items-center gap-1 text-white/80 hover:text-white transition-colors text-xs p-1">
                          <Shield className="w-5 h-5" />
                          <span className="font-medium hidden lg:inline">Admin</span>
                        </button>
                      </DropdownMenuTrigger>
                    </TooltipTrigger>
                    <TooltipContent>Admin Panel</TooltipContent>
                  </Tooltip>
                      <DropdownMenuContent align="end">
                        {adminPages.map((item) => (
                          <DropdownMenuItem key={item.page} asChild>
                            <Link to={createPageUrl(item.page)} className="flex items-center gap-2">
                              <item.icon className="w-4 h-4" />
                              {item.name}
                            </Link>
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                </DropdownMenu>
              )}

              {user ? (
                <DropdownMenu>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <DropdownMenuTrigger asChild>
                        <button className="flex items-center text-white hover:text-white/80 transition-colors p-1">
                          <UserIcon className="w-5 h-5" />
                        </button>
                      </DropdownMenuTrigger>
                    </TooltipTrigger>
                    <TooltipContent>Account</TooltipContent>
                  </Tooltip>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem asChild>
                          <Link to={createPageUrl("Profile")} className="flex items-center gap-2">
                            <UserIcon className="w-4 h-4" />
                            My Profile
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={handleLogout} className="text-red-400">
                          <LogOut className="w-4 h-4 mr-2" />
                          Sign Out
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                </DropdownMenu>
              ) : (
                <Button 
                  onClick={() => base44.auth.redirectToLogin()}
                  className="bg-[#FFB81C] hover:bg-[#e5a619] text-black font-semibold h-7 px-3 text-xs"
                >
                  Join
                </Button>
              )}
              </nav>
              </TooltipProvider>

            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden text-white"
            >
              <Menu className="w-7 h-7" />
            </button>
          </div>
        </div>
      </header>
      




      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-slate-900 fixed inset-0 z-40 pt-11" onClick={() => setMobileMenuOpen(false)}>
          <div className="px-4 py-6 space-y-2 overflow-y-auto h-full" onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setMobileMenuOpen(false)}
              className="absolute top-16 right-4 text-white p-2"
            >
              <X className="w-6 h-6" />
            </button>
              {publicPages.map((item) => (
                <Link
                  key={item.page}
                  to={createPageUrl(item.page)}
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-3 rounded-lg text-white hover:bg-white/10"
                >
                  <item.icon className="w-5 h-5" />
                  {item.name}
                </Link>
              ))}
              
              {user && userPages.map((item) => (
                <Link
                  key={item.page}
                  to={createPageUrl(item.page)}
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-3 rounded-lg text-white hover:bg-white/10"
                >
                  <item.icon className="w-5 h-5" />
                  {item.name}
                </Link>
              ))}

              {user && followingPages.map((item) => (
                <Link
                  key={item.page}
                  to={createPageUrl(item.page)}
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-3 rounded-lg text-white hover:bg-white/10"
                >
                  <item.icon className="w-5 h-5" />
                  {item.name}
                </Link>
              ))}

              {user && (
                <Link
                  to={createPageUrl("Notifications")}
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-3 rounded-lg text-white hover:bg-white/10 relative"
                >
                  <Bell className="w-5 h-5" />
                  Notifications
                  {unreadNotifications > 0 && (
                    <span className="ml-auto bg-red-500 text-white text-xs rounded-full px-2 py-1 font-bold">
                      {unreadNotifications}
                    </span>
                  )}
                </Link>
              )}

              {isAdmin && adminPages.map((item) => (
                <Link
                  key={item.page}
                  to={createPageUrl(item.page)}
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-3 rounded-lg text-white hover:bg-white/10"
                >
                  <item.icon className="w-5 h-5" />
                  {item.name}
                </Link>
              ))}

              <div className="pt-4 border-t border-white/10">
                {user ? (
                  <>
                    <Link
                      to={createPageUrl("Profile")}
                      onClick={() => setMobileMenuOpen(false)}
                      className="flex items-center gap-3 px-4 py-3 rounded-lg text-white hover:bg-white/10"
                    >
                      <UserIcon className="w-5 h-5" />
                      My Profile
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="flex items-center gap-3 px-4 py-3 rounded-lg text-red-300 hover:bg-white/10 w-full"
                    >
                      <LogOut className="w-5 h-5" />
                      Sign Out
                    </button>
                  </>
                ) : (
                  <Button 
                    onClick={() => base44.auth.redirectToLogin()}
                    className="w-full bg-white text-[#007A4D] hover:bg-white/90 font-semibold"
                  >
                    Join Now
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}

      {/* Main Content */}
      <main className="w-full m-0 p-0">
        {children}
      </main>
      
      <Toaster position="top-center" richColors />

      {/* Footer */}
      <footer className="bg-slate-900 text-white py-12 pb-16 sm:pb-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-0 md:gap-8 md:space-y-0 space-y-0">
            <div className="hidden md:flex flex-col items-start w-full md:w-auto">
              <div className="flex flex-col">
                <img 
                  src="https://qtrypzzcjebvfcihiynt.supabase.co/storage/v1/object/public/base44-prod/public/695eade926c226387ff83d9d/7c3eae2f4_ChatGPTImageJan24202605_34_40AM.png" 
                  alt="KopeloX" 
                  className="h-32 w-auto"
                />
                <p className="text-slate-400 text-sm max-w-[200px] text-left transform -translate-y-12">
                  Collective culture and national mobilisation platform.
                </p>
              </div>
            </div>

            <div className="flex-1 md:text-center w-full md:mt-0">
              <div className="md:hidden mb-6 flex flex-col items-center">
                <img 
                  src="https://qtrypzzcjebvfcihiynt.supabase.co/storage/v1/object/public/base44-prod/public/695eade926c226387ff83d9d/7c3eae2f4_ChatGPTImageJan24202605_34_40AM.png" 
                  alt="KopeloX" 
                  className="h-20 w-auto -mb-6"
                />
                <p className="text-slate-400 text-xs max-w-[160px] text-center leading-tight">
                  Collective culture and national mobilisation platform.
                </p>
              </div>
              <h4 className="font-semibold mb-3 text-center md:text-center">Bafana Bafana 2026</h4>
              <p className="text-slate-400 text-sm max-w-md mx-auto text-center md:text-center mb-8 md:mb-0">
                One Voice RSA — Uniting South Africans in support of our national team at the FIFA World Cup 2026.
              </p>
            </div>

            <div className="md:text-right w-full md:w-auto text-center md:text-right">
              <p style={{ color: currentTheme.secondary }} className="font-bold text-xl whitespace-nowrap">
                No DNA.<br />Just RSA.
              </p>
            </div>
          </div>
          
          <div className="border-t border-slate-800 mt-8 pt-8 text-center text-slate-400 text-sm px-6 sm:px-4">
            <p className="break-words">© 2025 KopeloX. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
