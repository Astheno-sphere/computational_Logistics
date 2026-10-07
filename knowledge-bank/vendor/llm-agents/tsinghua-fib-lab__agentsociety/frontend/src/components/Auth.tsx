import {
    createContext,
    type ReactNode,
    useContext,
    useEffect,
    useState,
} from "react";
import { jwtDecode, type JwtPayload } from "jwt-decode";
import Sdk from "casdoor-js-sdk";
import type { SdkConfig } from "casdoor-js-sdk/lib/esm/sdk";

export const sdkConfig = {
    serverUrl: "https://login.fiblab.net",
    clientId: "7ffcbfe4ae0fcb2c0d63",
    appName: "agentsociety",
    organizationName: "fiblab",
    redirectPath: "/callback",
    signinPath: "/api/signin",
};

export const DEMO_USER_TOKEN = "DEMO_USER_TOKEN";

let casdoorSdk: Sdk | undefined;

/** 获取全局的 Casdoor SDK，如果还没有初始化，就用 `config` 新建一个。*/
export function getCasdoorSdk(config: SdkConfig) {
    return (casdoorSdk ??= new Sdk(config));
}

/** 获取全局的 access token。未登录时返回 `null`。*/
export function getAccessToken() {
    const token = localStorage.getItem("access_token");
    if (token === DEMO_USER_TOKEN) {
        return token;
    }
    // 检查 token 是否过期
    if (token) {
        const decoded = jwtDecode<AccessTokenPayload>(token);
        if (decoded.exp < Date.now() / 1000) {
            localStorage.removeItem("access_token");
            return null;
        }
    }
    return token;
}

export interface AccessTokenPayload extends JwtPayload {
    /**
     * Token 的发布者。见 [JWT 标准][1]。
     *
     * [1]: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1
     */
    iss: string;
    /**
     * Token 的主题。见 [JWT 标准][1]。
     *
     * [1]: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1
     */
    sub: string;
    /**
     * Token 的目标应用 ID。见 [JWT 标准][1]。
     *
     * [1]: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1
     */
    aud: string[];
    /**
     * 使用 Token 的应用 ID。见 [JWT 标准][1]。
     *
     * [1]: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1
     */
    azp: string;
    /**
     * Token 的唯一标识符。见 [JWT 标准][1]。
     *
     * [1]: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1
     */
    jti: string;
    /** Token 的过期时间（Unix 时间戳）。*/
    exp: number;
    /** Token 的生效时间（Unix 时间戳）。*/
    nbf: number;
    /** Token 的签发时间（Unix 时间戳）。*/
    iat: number;

    /** 用户的登录名。*/
    name: string;
    /** 用户的 UUID。*/
    id: string;
    /** 用户的显示名。*/
    displayName: string;
    /** 用户的头像 URL。*/
    avatar: string;
    /** 用户的邮件地址。*/
    email: string;
    /** 用户的手机号。*/
    phone: string;

    owner: "fiblab";
    tokenType: "access-token";
    scope: "profile";
}

/** 获取全局的 access token 并解码。解码得到的 payload 中也有一些用户信息，
 * 可以在一定程度上代替通过 API 获取用户信息。未登录时返回 `null`。*/
export function getDecodedAccessToken() {
    const token = getAccessToken();
    if (token === null) return;
    return jwtDecode<AccessTokenPayload>(token);
}

export interface UserInfo {
    /**
     * Token 的发布者。见 [JWT 标准][1]。
     *
     * [1]: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1
     */
    iss: string;
    /**
     * Token 的主题。见 [JWT 标准][1]。
     *
     * [1]: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1
     */
    sub: string;
    /**
     * Token 的目标应用 ID。见 [JWT 标准][1]。
     *
     * [1]: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1
     */
    aud: string;
    /** 用户的全名（显示名）。*/
    name: string;
    /** 短用户名（登录名）。*/
    prefered_username: string;
    /** 用户的邮件地址。*/
    email?: string;
    /** 用户的邮件地址是否已确认。*/
    email_verified?: boolean;
    /** 用户的手机号。*/
    phone?: string;
    /** 用户的头像 URL。*/
    picture: string;
    /** 用户的地址。*/
    address?: string;
    /** 用户所属的用户组。*/
    groups: string[];
    /** 用户的角色。*/
    roles: string[];
}

const AuthContext = createContext<UserInfo | undefined>(undefined);

/** 获取用户信息。必须在开启了 `onlineCheck` 的 {@linkcode AuthProvider} 内部使用，否则返回 `undefined`。*/
export function useUserInfo() {
    return useContext(AuthContext);
}

export interface AuthProviderProps {
    /**
     * Casdoor SDK 的配置。
     *
     * **注意**：初始化的 SDK 将保存为全局变量，因此一个项目内不可有多个不同的 SDK 配置。
     * 通过 {@linkcode getCasdoorSdk} 可以获取到全局的 SDK。
     */
    sdkConfig: SdkConfig;
    /**
     * 是否联网检查用户登录状态有效性。如果检查，那么在内部还可以使用 {@linkcode useUserInfo} 访问到用户信息。
     * @default false
     */
    onlineCheck?: boolean;
    /**
     * 如果开启了 `onlineCheck`，在检查过程中时向用户显示的加载界面。
     * @default "Logging in……"
     */
    loading?: ReactNode;
    /** 用户登录后显示的内容。*/
    children: ReactNode;
    /**
     * 是否立即跳转到登录页面。
     * @default true
     */
    gotoLoginImmediately?: boolean;
}

/**
 * 确保只有已登录的用户可以访问到内部的内容，未登录的用户将被重定向到登录界面。
 */
export function AuthProvider(props: AuthProviderProps): ReactNode {
    const sdk = getCasdoorSdk(props.sdkConfig);
    const token = getAccessToken();
    const [userInfo, setUserInfo] = useState<UserInfo>();
    useEffect(
        () => {
            if (token === null) {
                if (props.gotoLoginImmediately === true || props.gotoLoginImmediately === undefined) {
                    location.href = sdk.getSigninUrl();
                }
            } else {
                if (props.onlineCheck) {
                    sdk.getUserInfo(token).then((_resp) => {
                        // sdk 的类型声明有误
                        const resp = _resp as unknown as UserInfo | { status: "error" };
                        if ("status" in resp) {
                            location.href = sdk.getSigninUrl();
                        } else {
                            setUserInfo(resp);
                        }
                    });
                }
            }
        },
        [token, props.onlineCheck], // eslint-disable-line react-hooks/exhaustive-deps
    );
    if (props.gotoLoginImmediately === false) {
        return (
            <AuthContext.Provider value={userInfo}>
                {props.children}
            </AuthContext.Provider>
        );
    }
    return token === null ? (
        "Skipping login……"
    ) : props.onlineCheck && userInfo === undefined ? (
        (props.loading ?? "Logging in……")
    ) : (
        <AuthContext.Provider value= { userInfo } >
        { props.children }
    </AuthContext.Provider>
  );
}

export interface AuthCallbackProps {
    /**
     * Casdoor SDK 的配置。
     *
     * **注意**：初始化的 SDK 将保存为全局变量，因此一个项目内不可有多个不同的 SDK 配置。
     * 通过 {@linkcode getCasdoorSdk} 可以获取到全局的 SDK。
     */
    sdkConfig: SdkConfig;
    /** 登录的 API 源点，末尾不带 `/`。*/
    signinOrigin: string;
    /**
     * 登陆的 API 路径。
     * @default "/api/signin"
     */
    signinPath?: string;
    /**
     * 跳转时的回调。可以使用 React Router 的跳转函数。
     * @default () => { location.href = "/"; }
     */
    onRedirect?: () => void;
    /**
     * 发生错误时显示的内容。
     * @default (err) => err.toString()
     */
    error?: (err: unknown) => ReactNode;
    /**
     * 跳转前显示的内容。
     * @default "Skipping login……"
     */
    children?: ReactNode;
}

/** 登录的回调页面。*/
export function AuthCallback(props: AuthCallbackProps): ReactNode {
    const [error, setError] = useState<unknown>();
    useEffect(
        () => {
            getCasdoorSdk(props.sdkConfig)
                .signin(props.signinOrigin, props.signinPath)
                .then((_resp) => {
                    // sdk 的类型声明有误
                    const resp = _resp as unknown as { token?: string };
                    if (!resp.token) {
                        throw new Error(
                            "Login API returned an abnormal result: " + JSON.stringify(resp),
                        );
                    }
                    localStorage.setItem("access_token", resp.token);
                    if (props.onRedirect) {
                        props.onRedirect();
                    } else {
                        location.href = "/";
                    }
                })
                .catch((err) => setError(err));
        },
        [], // eslint-disable-line react-hooks/exhaustive-deps
    );
    return error
        ? props.error
            ? props.error(error)
            : (error as object).toString()
        : (props.children ?? "Skipping login……");
}
