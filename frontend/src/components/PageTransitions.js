import { motion } from 'framer-motion';

// Page transition wrapper with zoom effect
export const PageTransition = ({ children }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 1.05 }}
      transition={{ 
        duration: 0.4, 
        ease: [0.43, 0.13, 0.23, 0.96] // Custom easing
      }}
    >
      {children}
    </motion.div>
  );
};

// Button click ripple animation
export const ButtonRipple = ({ children, onClick, className = "", ...props }) => {
  return (
    <motion.button
      whileTap={{ scale: 0.95 }}
      whileHover={{ scale: 1.02 }}
      onClick={onClick}
      className={className}
      {...props}
    >
      {children}
    </motion.button>
  );
};

// Card entrance animation
export const CardAnimation = ({ children, delay = 0 }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
};

// Stagger children animation
export const StaggerContainer = ({ children }) => {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        visible: {
          transition: {
            staggerChildren: 0.1
          }
        }
      }}
    >
      {children}
    </motion.div>
  );
};

export const StaggerItem = ({ children }) => {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 10 },
        visible: { opacity: 1, y: 0 }
      }}
    >
      {children}
    </motion.div>
  );
};
