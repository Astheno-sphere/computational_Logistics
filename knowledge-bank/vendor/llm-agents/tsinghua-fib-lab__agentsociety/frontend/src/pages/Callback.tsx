 
import { AuthCallback, sdkConfig } from "../components/Auth";

const Callback = () => {
    return (
        <AuthCallback
            sdkConfig={sdkConfig}
            signinOrigin=""
            signinPath="/api/signin"
            onRedirect={() => {
                window.location.href = localStorage.getItem("backHref") ?? "/";
            }}
        />
    );
}

export default Callback;