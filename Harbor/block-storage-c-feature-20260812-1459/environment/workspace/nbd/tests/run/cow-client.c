/*
 * Test client for copy-on-write exports of nbd-server.
 *
 * The expected contents of the export are a deterministic pattern, so
 * the client can verify data without keeping a copy of what was read.
 *
 * Modes:
 * - init <file>
 *   write the pattern into <file>, creating it. This is meant to be
 *   the master file of a copy-on-write export.
 * - checkfile <file>
 *   verify that the file on disk contains the pattern and nothing else.
 * - write <host> <port> <export>
 *   connect, overwrite a few regions (page-aligned and unaligned), and
 *   verify that reads return the written data where writes happened and
 *   the original pattern everywhere else.
 * - read <host> <port> <export>
 *   connect and verify that the export contains only the original
 *   pattern; this is what a copy-on-write export must show again after
 *   the previous connection was disconnected.
 *
 * Exit status is 0 on success, 1 on failure.
 */

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

#include "config.h"
#include "lfs.h"

#define MY_NAME "cow-client"
#include "cliserv.h"

#define DEVICESIZE (1024 * 1024)
#define CHUNKSIZE (64 * 1024)

struct wr {
	uint64_t off;
	uint32_t len;
	unsigned char byte;
};

/*
 * The writes performed in "write" mode, in order. They cover an
 * aligned full page, a partial write straddling a page boundary, a
 * multi-page write with unaligned start and end, and a rewrite of an
 * already dirty page.
 */
static struct wr writes[] = {
	{ 0, 4096, 0xA1 },
	{ 4000, 200, 0xB2 },
	{ 100000, 5000, 0xC3 },
	{ 4000, 200, 0xD4 },
};

static unsigned char pattern_byte(uint64_t off) {
	return (off * 7 + 13) & 0xff;
}

static void fill_pattern(unsigned char *buf, uint64_t off, size_t len) {
	size_t i;

	for (i = 0; i < len; i++) {
		buf[i] = pattern_byte(off + i);
	}
}

static void fail(const char *msg) {
	fprintf(stderr, "cow-client: %s\n", msg);
	exit(1);
}

static int connect_tcp(const char *host, const char *port) {
	struct addrinfo hints;
	struct addrinfo *res;
	int sock;
	int e;

	memset(&hints, 0, sizeof(hints));
	hints.ai_family = AF_UNSPEC;
	hints.ai_socktype = SOCK_STREAM;
	if((e = getaddrinfo(host, port, &hints, &res))) {
		fprintf(stderr, "cow-client: getaddrinfo: %s\n",
			gai_strerror(e));
		exit(1);
	}
	sock = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
	if(sock < 0) {
		fail("could not create socket");
	}
	if(connect(sock, res->ai_addr, res->ai_addrlen) < 0) {
		fail("could not connect");
	}
	freeaddrinfo(res);
	return sock;
}

static void negotiate_go(int sock, const char *exportname) {
	char init_passwd[8];
	uint64_t magic;
	uint16_t sflags;
	uint32_t cflags;
	uint32_t namelen;
	uint32_t optlen;
	uint32_t opt;
	uint32_t type;
	uint32_t len;
	uint16_t n_requests;
	struct {
		uint64_t magic;
		uint32_t opt;
		uint32_t len;
	} __attribute__((packed)) optreq;
	struct {
		uint64_t magic;
		uint32_t opt;
		uint32_t type;
		uint32_t len;
	} __attribute__((packed)) optrep;
	char scratch[4096];

	if(readit(sock, init_passwd, 8) < 0) {
		fail("could not read initial magic");
	}
	if(memcmp(init_passwd, INIT_PASSWD, 8) != 0) {
		fail("initial magic mismatch");
	}
	if(readit(sock, &magic, 8) < 0) {
		fail("could not read options magic");
	}
	magic = ntohll(magic);
	if(magic != 0x49484156454F5054LL) {
		fail("options magic mismatch");
	}
	if(readit(sock, &sflags, 2) < 0) {
		fail("could not read handshake flags");
	}
	cflags = htonl(NBD_FLAG_C_FIXED_NEWSTYLE | NBD_FLAG_C_NO_ZEROES);
	if(writeit(sock, &cflags, 4) < 0) {
		fail("could not send client flags");
	}

	/* NBD_OPT_GO */
	namelen = strlen(exportname);
	n_requests = 0;
	optlen = namelen + sizeof(namelen) + sizeof(n_requests);
	optreq.magic = htonll(0x49484156454F5054LL);
	optreq.opt = htonl(NBD_OPT_GO);
	optreq.len = htonl(optlen);
	namelen = htonl(namelen);
	n_requests = htons(n_requests);
	if(writeit(sock, &optreq, sizeof(optreq)) < 0) {
		fail("could not send option request");
	}
	if(writeit(sock, &namelen, sizeof(namelen)) < 0) {
		fail("could not send export name length");
	}
	if(writeit(sock, exportname, ntohl(namelen)) < 0) {
		fail("could not send export name");
	}
	if(writeit(sock, &n_requests, sizeof(n_requests)) < 0) {
		fail("could not send info request count");
	}

	/* eat option replies until we get an ACK */
	while(1) {
		if(readit(sock, &optrep, sizeof(optrep)) < 0) {
			fail("could not read option reply");
		}
		if(ntohll(optrep.magic) != NBD_OPT_REPLY_MAGIC) {
			fail("option reply magic mismatch");
		}
		type = ntohl(optrep.type);
		len = ntohl(optrep.len);
		if(len > sizeof(scratch)) {
			fail("option reply too long");
		}
		if(readit(sock, scratch, len) < 0) {
			fail("could not read option reply data");
		}
		if(type & NBD_REP_FLAG_ERROR) {
			fail("server sent error reply to NBD_OPT_GO");
		}
		if(type == NBD_REP_ACK) {
			opt = ntohl(optrep.opt);
			if(opt != NBD_OPT_GO) {
				fail("ACK for the wrong option");
			}
			return;
		}
	}
}

static int do_io(int sock, uint32_t cmd, uint64_t from, unsigned char *buf,
		 uint32_t len, uint32_t *rerror) {
	struct nbd_request req;
	struct nbd_reply rep;
	static uint64_t cookie = 0;

	req.magic = htonl(NBD_REQUEST_MAGIC);
	req.type = htonl(cmd);
	req.cookie = htonll(++cookie);
	req.from = htonll(from);
	req.len = htonl(len);
	if(writeit(sock, &req, sizeof(req)) < 0) {
		return -1;
	}
	if(cmd == NBD_CMD_WRITE) {
		if(writeit(sock, buf, len) < 0) {
			return -1;
		}
	}
	if(readit(sock, &rep, sizeof(rep)) < 0) {
		return -1;
	}
	if(rep.magic != htonl(NBD_REPLY_MAGIC)) {
		fail("reply magic mismatch");
	}
	if(rep.cookie != req.cookie) {
		fail("cookie mismatch");
	}
	*rerror = ntohl(rep.error);
	if(*rerror != 0) {
		return 0;
	}
	if(cmd == NBD_CMD_READ) {
		if(readit(sock, buf, len) < 0) {
			return -1;
		}
	}
	return 0;
}

/*
 * Read the whole export and compare it against expected.
 */
static void verify_export(int sock, const unsigned char *expected,
			  const char *what) {
	unsigned char buf[CHUNKSIZE];
	uint64_t off;
	uint32_t len;
	uint32_t error;

	for(off = 0; off < DEVICESIZE; off += len) {
		len = CHUNKSIZE;
		if(len > DEVICESIZE - off) {
			len = DEVICESIZE - off;
		}
		if(do_io(sock, NBD_CMD_READ, off, buf, len, &error) < 0) {
			fail("read failed while verifying");
		}
		if(error != 0) {
			fprintf(stderr,
				"cow-client: read error %u at offset %llu"
				" while verifying %s\n",
				error, (unsigned long long)off, what);
			exit(1);
		}
		if(memcmp(buf, expected + off, len) != 0) {
			fprintf(stderr,
				"cow-client: data mismatch at offset %llu"
				" while verifying %s\n",
				(unsigned long long)off, what);
			exit(1);
		}
	}
}

static void disconnect(int sock) {
	struct nbd_request req;

	/* The server does not send a reply to NBD_CMD_DISC */
	req.magic = htonl(NBD_REQUEST_MAGIC);
	req.type = htonl(NBD_CMD_DISC);
	req.cookie = 0;
	req.from = 0;
	req.len = 0;
	if(writeit(sock, &req, sizeof(req)) < 0) {
		fail("disconnect failed");
	}
	close(sock);
}

static int do_init(const char *fname) {
	unsigned char buf[CHUNKSIZE];
	uint64_t off;
	int fd;

	fd = open(fname, O_WRONLY | O_CREAT | O_TRUNC, 0644);
	if(fd < 0) {
		fail("could not create master file");
	}
	for(off = 0; off < DEVICESIZE; off += sizeof(buf)) {
		fill_pattern(buf, off, sizeof(buf));
		if(writeit(fd, buf, sizeof(buf)) < 0) {
			fail("could not write master file");
		}
	}
	if(ftruncate(fd, DEVICESIZE) < 0) {
		fail("could not truncate master file");
	}
	close(fd);
	return 0;
}

static int do_checkfile(const char *fname) {
	unsigned char buf[CHUNKSIZE];
	unsigned char expected[CHUNKSIZE];
	uint64_t off;
	size_t len;
	int fd;
	ssize_t res;

	fd = open(fname, O_RDONLY);
	if(fd < 0) {
		fail("could not open master file");
	}
	for(off = 0; off < DEVICESIZE; off += len) {
		len = sizeof(buf);
		if(len > DEVICESIZE - off) {
			len = DEVICESIZE - off;
		}
		res = read(fd, buf, len);
		if(res != (ssize_t)len) {
			fail("short read on master file");
		}
		fill_pattern(expected, off, len);
		if(memcmp(buf, expected, len) != 0) {
			fprintf(stderr,
				"cow-client: master file changed at offset"
				" %llu\n", (unsigned long long)off);
			return 1;
		}
	}
	close(fd);
	return 0;
}

static int do_write(const char *host, const char *port, const char *export) {
	static unsigned char expected[DEVICESIZE];
	static unsigned char buf[CHUNKSIZE];
	unsigned int i;
	uint32_t error;
	int sock;

	fill_pattern(expected, 0, DEVICESIZE);
	sock = connect_tcp(host, port);
	negotiate_go(sock, export);
	for(i = 0; i < sizeof(writes) / sizeof(struct wr); i++) {
		memset(buf, writes[i].byte, writes[i].len);
		if(do_io(sock, NBD_CMD_WRITE, writes[i].off, buf,
			 writes[i].len, &error) < 0) {
			fail("write failed");
		}
		if(error != 0) {
			fprintf(stderr, "cow-client: server returned error"
				" %u for write %u\n", error, i);
			return 1;
		}
		memset(expected + writes[i].off, writes[i].byte,
		       writes[i].len);
	}
	/* written data must be visible to this connection immediately */
	verify_export(sock, expected, "written data");
	disconnect(sock);
	return 0;
}

static int do_read(const char *host, const char *port, const char *export) {
	static unsigned char expected[DEVICESIZE];
	int sock;

	fill_pattern(expected, 0, DEVICESIZE);
	sock = connect_tcp(host, port);
	negotiate_go(sock, export);
	verify_export(sock, expected, "original pattern");
	disconnect(sock);
	return 0;
}

int main(int argc, char *argv[]) {
	if(argc < 3) {
		fprintf(stderr,
			"usage: cow-client init <file>\n"
			"       cow-client checkfile <file>\n"
			"       cow-client write <host> <port> <export>\n"
			"       cow-client read <host> <port> <export>\n");
		return 1;
	}
	if(strcmp(argv[1], "init") == 0 && argc == 3) {
		return do_init(argv[2]);
	}
	if(strcmp(argv[1], "checkfile") == 0 && argc == 3) {
		return do_checkfile(argv[2]);
	}
	if((strcmp(argv[1], "write") == 0 || strcmp(argv[1], "read") == 0)
	   && argc == 5) {
		if(strcmp(argv[1], "write") == 0) {
			return do_write(argv[2], argv[3], argv[4]);
		}
		return do_read(argv[2], argv[3], argv[4]);
	}
	fprintf(stderr, "cow-client: invalid arguments\n");
	return 1;
}
