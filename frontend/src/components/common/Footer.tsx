import React from "react";
import { Activity, Github, Shield, Cpu } from "lucide-react";

export const Footer: React.FC = () => {
  return (
    <footer className="bg-slate-950 border-t border-slate-900 text-slate-400 py-10 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <p className="text-white font-semibold text-sm">MotionAI Skill Assessment Platform</p>
              <p className="text-xs text-slate-500">FastDTW • TCPFormer 3D Pose • Clean Architecture</p>
            </div>
          </div>

          <div className="flex items-center gap-6 text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-emerald-400" />
              Celery Worker Async AI
            </span>
            <span className="flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-blue-400" />
              JWT RBAC Protected
            </span>
          </div>

          <p className="text-xs text-slate-500">
            © 2026 Skill Assessment Platform. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
};
