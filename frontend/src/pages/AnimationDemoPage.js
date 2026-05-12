import { useState } from "react";
import { ArrowLeft, TrendingUp, Users, DollarSign, Activity, PlayCircle, CheckCircle, AlertCircle } from "lucide-react";
import { Link } from "react-router-dom";

export default function AnimationDemoPage() {
  const [style, setStyle] = useState("option1"); // option1 or option2
  const [count, setCount] = useState(0);
  const [progress, setProgress] = useState(45);
  const [showModal, setShowModal] = useState(false);

  const incrementCount = () => setCount(prev => Math.min(prev + 10, 100));

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 text-white p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <Link to="/" className="inline-flex items-center gap-2 text-zinc-400 hover:text-white mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>
        
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2">🎨 Animation Style Demo</h1>
            <p className="text-zinc-400">Test both animation options before applying to your project</p>
          </div>
          
          {/* Style Toggle */}
          <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
            <p className="text-sm text-zinc-400 mb-3">Select Animation Style:</p>
            <div className="flex gap-3">
              <button
                onClick={() => setStyle("option1")}
                className={`px-6 py-3 rounded-lg font-medium transition-all ${
                  style === "option1"
                    ? "bg-emerald-600 text-white shadow-lg shadow-emerald-500/50"
                    : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                }`}
              >
                Option 1: Minimalist
              </button>
              <button
                onClick={() => setStyle("option2")}
                className={`px-6 py-3 rounded-lg font-medium transition-all ${
                  style === "option2"
                    ? "bg-purple-600 text-white shadow-lg shadow-purple-500/50"
                    : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                }`}
              >
                Option 2: Dynamic
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto space-y-8">
        {/* Stats Cards Demo */}
        <section>
          <h2 className="text-2xl font-bold mb-4">📊 Dashboard Stats Cards</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard 
              icon={<TrendingUp className="w-6 h-6" />}
              title="Total Conversions"
              value="2,547"
              change="+12.5%"
              color="emerald"
              style={style}
            />
            <StatCard 
              icon={<Users className="w-6 h-6" />}
              title="Active Jobs"
              value="18"
              change="+3"
              color="blue"
              style={style}
            />
            <StatCard 
              icon={<DollarSign className="w-6 h-6" />}
              title="Revenue"
              value="$12,450"
              change="+8.2%"
              color="purple"
              style={style}
            />
            <StatCard 
              icon={<Activity className="w-6 h-6" />}
              title="Success Rate"
              value="94.3%"
              change="+2.1%"
              color="rose"
              style={style}
            />
          </div>
        </section>

        {/* Progress & Buttons Demo */}
        <section>
          <h2 className="text-2xl font-bold mb-4">🎯 Progress & Interactive Elements</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Progress Bar */}
            <div className={`bg-zinc-900 rounded-xl p-6 border border-zinc-800 ${
              style === "option1" ? "hover:border-emerald-500/50 transition-all duration-300" 
              : "hover:border-purple-500 hover:shadow-lg hover:shadow-purple-500/20 transition-all duration-500"
            }`}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Job Progress</h3>
                <span className="text-emerald-400 font-bold">{progress}%</span>
              </div>
              <ProgressBar progress={progress} style={style} />
              <div className="mt-4 flex gap-2">
                <button 
                  onClick={() => setProgress(prev => Math.min(prev + 10, 100))}
                  className={`flex-1 py-2 px-4 rounded-lg font-medium ${
                    style === "option1"
                      ? "bg-emerald-600 hover:bg-emerald-500 hover:scale-105 transition-all duration-200"
                      : "bg-gradient-to-r from-emerald-600 to-green-500 hover:from-emerald-500 hover:to-green-400 hover:scale-110 active:scale-95 transition-all duration-400"
                  }`}
                >
                  +10%
                </button>
                <button 
                  onClick={() => setProgress(0)}
                  className={`flex-1 py-2 px-4 rounded-lg font-medium ${
                    style === "option1"
                      ? "bg-zinc-800 hover:bg-zinc-700 transition-all duration-200"
                      : "bg-zinc-800 hover:bg-zinc-700 hover:scale-105 active:scale-95 transition-all duration-400"
                  }`}
                >
                  Reset
                </button>
              </div>
            </div>

            {/* Counter */}
            <div className={`bg-zinc-900 rounded-xl p-6 border border-zinc-800 ${
              style === "option1" ? "hover:border-purple-500/50 transition-all duration-300" 
              : "hover:border-purple-500 hover:shadow-lg hover:shadow-purple-500/20 transition-all duration-500"
            }`}>
              <h3 className="text-lg font-semibold mb-4">Conversion Counter</h3>
              <div className={`text-6xl font-bold text-center my-8 ${
                style === "option2" ? "transition-all duration-500 scale-110" : "transition-all duration-300"
              }`}>
                {count}
              </div>
              <button 
                onClick={incrementCount}
                className={`w-full py-3 px-4 rounded-lg font-medium ${
                  style === "option1"
                    ? "bg-purple-600 hover:bg-purple-500 hover:scale-105 transition-all duration-200"
                    : "bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-500 hover:to-pink-400 hover:scale-110 active:scale-95 transition-all duration-400"
                }`}
              >
                Add Conversion (+10)
              </button>
            </div>
          </div>
        </section>

        {/* Status Badges Demo */}
        <section>
          <h2 className="text-2xl font-bold mb-4">🏷️ Status Badges & Alerts</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatusCard 
              icon={<PlayCircle className="w-8 h-8" />}
              title="Running Job"
              status="active"
              message="Processing 45 conversions..."
              style={style}
            />
            <StatusCard 
              icon={<CheckCircle className="w-8 h-8" />}
              title="Completed"
              status="success"
              message="100 conversions successful!"
              style={style}
            />
            <StatusCard 
              icon={<AlertCircle className="w-8 h-8" />}
              title="Action Needed"
              status="warning"
              message="Low proxy balance"
              style={style}
            />
          </div>
        </section>

        {/* Modal Demo */}
        <section>
          <h2 className="text-2xl font-bold mb-4">💬 Modal & Dialogs</h2>
          <button
            onClick={() => setShowModal(true)}
            className={`px-8 py-4 rounded-xl font-semibold text-lg ${
              style === "option1"
                ? "bg-emerald-600 hover:bg-emerald-500 hover:scale-105 transition-all duration-200"
                : "bg-gradient-to-r from-emerald-600 to-cyan-500 hover:from-emerald-500 hover:to-cyan-400 hover:scale-110 active:scale-95 transition-all duration-400 shadow-lg hover:shadow-emerald-500/50"
            }`}
          >
            Open Demo Modal
          </button>
        </section>

        {/* Live Activity Demo */}
        <section>
          <h2 className="text-2xl font-bold mb-4">📝 Live Activity Feed</h2>
          <div className="bg-zinc-900 rounded-xl p-6 border border-zinc-800 space-y-3">
            <ActivityItem 
              text="Visit #1 completed - Conversion successful"
              time="2s ago"
              type="success"
              style={style}
            />
            <ActivityItem 
              text="Visit #2 in progress - Filling form..."
              time="5s ago"
              type="info"
              style={style}
            />
            <ActivityItem 
              text="Visit #3 started - Opening browser..."
              time="8s ago"
              type="active"
              style={style}
            />
          </div>
        </section>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4"
             onClick={() => setShowModal(false)}>
          <div 
            className={`bg-zinc-900 rounded-2xl p-8 max-w-md w-full border border-zinc-800 ${
              style === "option1" 
                ? "animate-fadeScale" 
                : "animate-bounceZoom"
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-2xl font-bold mb-4">🎉 Success!</h3>
            <p className="text-zinc-400 mb-6">
              Your RUT job has been created successfully. 100 conversions will be processed with the optimized settings.
            </p>
            <button
              onClick={() => setShowModal(false)}
              className={`w-full py-3 rounded-lg font-medium ${
                style === "option1"
                  ? "bg-emerald-600 hover:bg-emerald-500 transition-all duration-200"
                  : "bg-gradient-to-r from-emerald-600 to-green-500 hover:scale-105 active:scale-95 transition-all duration-400"
              }`}
            >
              Got it!
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Components
function StatCard({ icon, title, value, change, color, style }) {
  const colors = {
    emerald: "from-emerald-500 to-green-600",
    blue: "from-blue-500 to-cyan-600",
    purple: "from-purple-500 to-pink-600",
    rose: "from-rose-500 to-red-600",
  };

  return (
    <div className={`bg-zinc-900 rounded-xl p-6 border border-zinc-800 ${
      style === "option1" 
        ? "hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300 hover:border-zinc-700"
        : "hover:scale-105 hover:rotate-1 hover:shadow-2xl hover:shadow-emerald-500/20 transition-all duration-500 hover:border-emerald-500"
    }`}>
      <div className={`p-3 rounded-lg bg-gradient-to-br ${colors[color]} w-fit mb-4`}>
        {icon}
      </div>
      <h3 className="text-sm text-zinc-400 mb-1">{title}</h3>
      <div className="flex items-end justify-between">
        <p className={`text-3xl font-bold ${
          style === "option2" ? "transition-all duration-300" : ""
        }`}>{value}</p>
        <span className="text-sm text-emerald-400 font-medium">{change}</span>
      </div>
    </div>
  );
}

function ProgressBar({ progress, style }) {
  return (
    <div className="w-full h-3 bg-zinc-800 rounded-full overflow-hidden">
      <div 
        className={`h-full bg-gradient-to-r from-emerald-500 to-green-400 ${
          style === "option1"
            ? "transition-all duration-500 ease-out"
            : "transition-all duration-700 ease-out animate-pulse"
        }`}
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}

function StatusCard({ icon, title, status, message, style }) {
  const statusColors = {
    active: "border-blue-500/50 bg-blue-500/10",
    success: "border-emerald-500/50 bg-emerald-500/10",
    warning: "border-amber-500/50 bg-amber-500/10",
  };

  const iconColors = {
    active: "text-blue-400",
    success: "text-emerald-400",
    warning: "text-amber-400",
  };

  return (
    <div className={`bg-zinc-900 rounded-xl p-6 border ${statusColors[status]} ${
      style === "option1"
        ? "hover:shadow-lg transition-all duration-300"
        : "hover:scale-105 hover:-rotate-1 transition-all duration-500 hover:shadow-xl"
    }`}>
      <div className={`${iconColors[status]} mb-4 ${
        style === "option2" ? "animate-pulse" : ""
      }`}>
        {icon}
      </div>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <p className="text-sm text-zinc-400">{message}</p>
    </div>
  );
}

function ActivityItem({ text, time, type, style }) {
  const dotColors = {
    success: "bg-emerald-400",
    info: "bg-blue-400",
    active: "bg-purple-400",
  };

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg bg-zinc-800/50 ${
      style === "option1"
        ? "hover:bg-zinc-800 transition-all duration-200"
        : "hover:bg-zinc-800 hover:translate-x-2 transition-all duration-400 animate-slideIn"
    }`}>
      <div className={`w-2 h-2 rounded-full mt-2 ${dotColors[type]} ${
        style === "option2" ? "animate-ping" : ""
      }`} />
      <div className="flex-1">
        <p className="text-sm text-zinc-300">{text}</p>
        <p className="text-xs text-zinc-500 mt-1">{time}</p>
      </div>
    </div>
  );
}
