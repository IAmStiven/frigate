import { useEffect, useRef, useState } from "react";

const useImageLoaded = (): [
  React.RefObject<HTMLImageElement | null>,
  boolean,
  () => void,
] => {
  const [loaded, setLoaded] = useState(false);
  const ref = useRef<HTMLImageElement>(null);

  const onLoad = () => {
    setLoaded(true);
  };

  useEffect(() => {
    if (ref.current && ref.current.complete && ref.current.naturalWidth > 0) {
      onLoad();
    }
  });

  return [ref, loaded, onLoad];
};

export default useImageLoaded;
