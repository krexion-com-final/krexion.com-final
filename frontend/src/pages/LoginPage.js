import { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import { Eye, EyeOff, Shield } from "lucide-react";
import { useBranding } from "../context/BrandingContext";
import ThemeToggle from "../components/ThemeToggle";
import WavyBackground from "../components/WavyBackground";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Legacy local wave canvas — kept only so existing JSX below doesn't break
// when the rest of the file still references <WavyBackgroundLegacy />.
// Swap-in path: we now use the shared `WavyBackground` component above.
const WavyBackgroundLegacy = ({ mousePosition }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const setCanvasSize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    setCanvasSize();
    window.addEventListener('resize', setCanvasSize);

    const lines = [];
    const lineCount = 150;
    
    for (let i = 0; i < lineCount; i++) {
      const startX = (canvas.width / lineCount) * i;
      lines.push({
        points: [],
        baseX: startX,
        amplitude: 30 + Math.random() * 50,
        frequency: 0.003 + Math.random() * 0.002,
        speed: 0.2 + Math.random() * 0.3,
        phase: Math.random() * Math.PI * 2,
        opacity: 0.15 + Math.random() * 0.25,
        mouseInfluence: 0,
        targetInfluence: 0
      });
      
      for (let y = 0; y <= canvas.height; y += 5) {
        lines[i].points.push({ y, x: 0 });
      }
    }

    let animationFrameId;
    let time = 0;

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      time += 0.01;

      lines.forEach((line) => {
        // Calculate distance from mouse
        const distanceX = Math.abs(line.baseX - mousePosition.x);
        
        // Only animate lines near cursor (spotlight effect)
        const spotlightRadius = 500; // Increased radius for better visibility
        const isInSpotlight = distanceX < spotlightRadius;
        
        // Calculate influence based on distance
        const targetInfluence = isInSpotlight 
          ? Math.max(0, (spotlightRadius - distanceX) / spotlightRadius)
          : 0;
        
        // Smooth easing
        line.targetInfluence = targetInfluence;
        line.mouseInfluence += (line.targetInfluence - line.mouseInfluence) * 0.08;

        // Only draw if line has some influence
        if (line.mouseInfluence > 0.01) {
          ctx.beginPath();
          // Opacity based on influence
          const finalOpacity = line.opacity * (0.3 + line.mouseInfluence * 0.7);
          ctx.strokeStyle = `rgba(79, 127, 255, ${finalOpacity})`;
          ctx.lineWidth = 1.2;

          line.points.forEach((point, index) => {
            // Wave amplitude scales with mouse influence
            const activeAmplitude = line.amplitude * line.mouseInfluence;
            
            const wave1 = Math.sin(point.y * line.frequency + time * line.speed + line.phase) * activeAmplitude;
            const wave2 = Math.sin(point.y * line.frequency * 0.5 + time * line.speed * 0.7) * (activeAmplitude * 0.4);
            
            // Additional mouse pull effect
            const distanceY = Math.abs(point.y - mousePosition.y);
            const totalDistance = Math.sqrt(distanceX * distanceX + distanceY * distanceY);
            const mouseEffect = Math.max(0, (300 - totalDistance) / 300) * 80 * line.mouseInfluence;
            
            const x = line.baseX + wave1 + wave2 + mouseEffect;
            
            if (index === 0) {
              ctx.moveTo(x, point.y);
            } else {
              ctx.lineTo(x, point.y);
            }
          });
          
          ctx.stroke();
        }
      });

      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', setCanvasSize);
    };
  }, [mousePosition]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ zIndex: 1 }}
    />
  );
};

export default function LoginPage() {
  const navigate = useNavigate();
  const { branding } = useBranding();
  const [showPassword, setShowPassword] = useState(false);
  const [activeTab, setActiveTab] = useState("login");
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [registerForm, setRegisterForm] = useState({ email: "", password: "", name: "" });
  const [loading, setLoading] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: window.innerWidth / 2, y: window.innerHeight / 2 });

  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/login`, loginForm);
      localStorage.setItem("token", response.data.access_token);
      localStorage.setItem("user", JSON.stringify(response.data.user));
      toast.success("Login successful!");
      navigate("/dashboard");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/register`, registerForm);
      localStorage.setItem("token", response.data.access_token);
      localStorage.setItem("user", JSON.stringify(response.data.user));
      toast.success("Registration successful!");
      navigate("/dashboard");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  // Desktop builds (Electron-packaged) hide the marketing left column and
  // center the login form. They also expose a "Buy License" / "Pricing"
  // shortcut that opens the user's default browser to krexion.com so the
  // customer can purchase or renew their license from inside the app.
  const isDesktop = process.env.REACT_APP_DESKTOP_BUILD === '1';

  return (
    <div className="min-h-screen relative overflow-hidden bg-black">
      <WavyBackground />
      
      <div className="absolute top-4 right-4 z-20 flex items-center gap-3">
        {isDesktop && (
          <a
            href="https://krexion.com/pricing"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs uppercase tracking-widest text-gray-400 hover:text-white transition-colors px-3 py-1.5 border border-gray-700 rounded-full"
            data-testid="desktop-buy-license-link"
          >
            Buy License
          </a>
        )}
        <ThemeToggle />
      </div>

      <div className={`relative z-10 min-h-screen flex items-center px-8 lg:px-20 ${isDesktop ? 'justify-center' : 'justify-between'}`}>
        {/* Left Side — marketing (cloud only). Hidden on desktop builds. */}
        {!isDesktop && (
        <div className="hidden lg:flex flex-col justify-center w-1/2 pr-12 animate-fadeIn">
          <div className="mb-4">
            <h1 className="text-white text-6xl font-bold mb-2">
              {branding.app_name || "KREXION"}
            </h1>
            <p className="text-gray-400 text-sm">EST 2025</p>
          </div>
          
          <h2 className="text-white text-5xl font-bold leading-tight mt-12">
            Start Small. Test One<br/>
            Traffic Source Before<br/>
            Scaling.
          </h2>
          
          <p className="text-gray-500 text-sm mt-8">
            Ready to elevate your affiliate game?<br/>
            Join us in turning community of marketers scaling their projects.
          </p>
        </div>
        )}

        {/* Right Side - Login Form */}
        <div className="w-full lg:w-1/2 max-w-md mx-auto animate-slideUp">
          <div className="backdrop-blur-md bg-black/40 rounded-3xl p-8 border border-gray-800 shadow-2xl">
            {/* Header */}
            <div className="text-center mb-8">
              <h3 className="text-white text-3xl font-bold mb-2">Hey There,</h3>
              <h4 className="text-4xl font-bold mb-4" style={{ color: "var(--brand-primary)" }}>Welcome Back!</h4>
              <p className="text-gray-400 text-sm">Let's get you back into your account.</p>
            </div>

            {/* Tabs - Simple Login/Register */}
            <div className="flex gap-2 mb-6">
              <button
                onClick={() => setActiveTab("login")}
                className="flex-1 py-3 px-4 rounded-xl font-medium transition-all duration-300"
                style={
                  activeTab === "login"
                    ? { backgroundColor: "var(--brand-primary)", color: "#fff", boxShadow: "0 10px 30px -10px var(--brand-primary)" }
                    : { backgroundColor: "rgba(20,20,30,0.6)", color: "#a0a0a0" }
                }
              >
                Login
              </button>
              <button
                onClick={() => setActiveTab("register")}
                className="flex-1 py-3 px-4 rounded-xl font-medium transition-all duration-300"
                style={
                  activeTab === "register"
                    ? { backgroundColor: "var(--brand-primary)", color: "#fff", boxShadow: "0 10px 30px -10px var(--brand-primary)" }
                    : { backgroundColor: "rgba(20,20,30,0.6)", color: "#a0a0a0" }
                }
              >
                Register
              </button>
            </div>

            {/* Login Form */}
            {activeTab === "login" ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-2">
                  <Input
                    type="email"
                    placeholder="shan.ali0744@gmail.com"
                    value={loginForm.email}
                    onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                    required
                    className="bg-white/90 text-black rounded-full py-6 px-6 focus-visible:ring-2 border-0"
                    style={{ '--tw-ring-color': 'var(--brand-primary)' }}
                    data-testid="login-email-input"
                  />
                </div>
                
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={loginForm.password}
                    onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                    required
                    className="bg-white/90 text-black rounded-full py-6 px-6 pr-12 focus-visible:ring-2 border-0"
                    style={{ '--tw-ring-color': 'var(--brand-primary)' }}
                    data-testid="login-password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-800"
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>

                <div className="flex items-center justify-between text-sm mt-4">
                  <Link to="/forgot-password" className="text-gray-400 transition hover:opacity-80" style={{ '--hover-color': 'var(--brand-primary)' }}>
                    Forgot password?
                  </Link>
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-8 py-3 rounded-full text-white hover:opacity-90 transition-all disabled:opacity-50"
                    style={{ background: "linear-gradient(135deg, var(--brand-primary), var(--brand-accent))", boxShadow: "0 10px 30px -10px var(--brand-primary)" }}
                    data-testid="login-submit-button"
                  >
                    {loading ? "Signing in..." : "Sign In →"}
                  </button>
                </div>
                
                {/* Admin Login Link */}
                <div className="mt-6 text-center">
                  <Link 
                    to="/admin" 
                    className="text-xs text-gray-500 transition flex items-center justify-center gap-2 hover:opacity-80"
                  >
                    <Shield size={14} />
                    Admin Login
                  </Link>
                </div>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <Input
                  type="text"
                  placeholder="Full Name"
                  value={registerForm.name}
                  onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                  required
                  className="bg-white/90 text-black rounded-full py-6 px-6 focus-visible:ring-2 border-0"
                  style={{ '--tw-ring-color': 'var(--brand-primary)' }}
                  data-testid="register-name-input"
                />
                <Input
                  type="email"
                  placeholder="Email Address"
                  value={registerForm.email}
                  onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                  required
                  className="bg-white/90 text-black rounded-full py-6 px-6 focus-visible:ring-2 border-0"
                  style={{ '--tw-ring-color': 'var(--brand-primary)' }}
                  data-testid="register-email-input"
                />
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="Password"
                    value={registerForm.password}
                    onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                    required
                    className="bg-white/90 text-black rounded-full py-6 px-6 pr-12 focus:ring-2 focus:ring-[#4F7FFF] border-0"
                    data-testid="register-password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-600"
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-full text-white hover:opacity-90 transition-all disabled:opacity-50"
                  style={{ background: "linear-gradient(135deg, var(--brand-primary), var(--brand-accent))", boxShadow: "0 10px 30px -10px var(--brand-primary)" }}
                  data-testid="register-submit-button"
                >
                  {loading ? "Creating..." : "Create Account"}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
