declare namespace Cloudflare {
	interface Env {
		DB?: D1Database;
		BUCKET?: R2Bucket;
		CJ_ADMIN_CODE?: string;
		CJ_ADMIN_ALLOWLIST?: string;
	}
}
