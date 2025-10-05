
/*
 * Ken's word-counter in C++
 */
#include <cstdlib>
#include <cstdio>
#include <thread>
#include <mutex>
#include <vector>
#include <cstring>
#include <map>
#include <array>
#include <semaphore>
#include <fcntl.h>
#include <unistd.h>
#include <atomic>
#include "utils.hpp"

const int MAXTHREADS = 64;
const int FDESCS = MAXTHREADS;
const int BASICBLOCK = 1024;
const int COMMON = 1024;
std::mutex lock;
char token_chars[512] = {0};
char buffers[MAXTHREADS][BASICBLOCK * 128];
int fdescs[FDESCS];
std::counting_semaphore<1> fcount(FDESCS);
std::counting_semaphore<1> opencount(0);
int free_ptr, next_ptr;
int nblocks = 16;
int BLOCKSIZE;
bool parallel_merge = false;
bool silent = false;
int nthreads = 1;
std::atomic_int file_count(0);
std::atomic_int expected_file_count(0);
std::atomic_int blocks_scanned(0);
std::atomic_int bytes_scanned(0);
std::counting_semaphore<1>* ready_for_merge[MAXTHREADS];

// C++ needs to know the declaration of anything it sees at the time it first sees it.  This particular method is used
// before I define it.  Mostly, I just wanted you to see an example of that.  The & means "by reference"
inline void found_something(int &, char *&, char *&, int &);

// Here, I am defining a new "type" that really is just an alias ("a different word for") a tree that has keys that are
// C++ strings and values that are integer counts
using WordCount = std::map<std::string, int>;

// We will be creating separate sub-counts on a per-thread basis and then later combining them.  This avoids a need to lock
// for each counting action, which would be very slow otherwise.
WordCount sub_count[MAXTHREADS];
WordCount total_count;

// Here is our file opener.  It would normally use the C++ FILE class, but it turns out we would need a lock (mutex) for each fread operation
// to avoid a form of conflict with the fopen operation.  That becomes quite slow, so instead this code uses the actual Linux system calls,
// open() and (in the word counter), read().  Doing direct Linux calls is allowed but a bit non-standard because this is such a low-level
// approach.  The big win is that I avoided extra creation of std::string objects, which cut my runtime costs down by about 50%
void fopener(char *dir)
{
	std::vector<fs::path> files_to_sweep;
	try
	{
		files_to_sweep = utils::find_all_files(dir, [](const std::string &extension){ return extension == ".h" || extension == ".c"; });
	}
	catch(const std::exception& e)
	{
		printf("File scanner unable to access folder %s\n", dir);
		exit(0);
	}

	int nfiles = files_to_sweep.size();
	if (!silent)
	{
		printf("In %s found %d files to scan\n", dir, nfiles);
		expected_file_count = nfiles;
	}
	while (nfiles--)
	{
		fcount.acquire();
		int slot = free_ptr % FDESCS;
		if ((fdescs[slot] = open(files_to_sweep[nfiles].c_str(), O_RDONLY)) == -1)
		{
			printf("Unable to open file: %s (errno %d)\n", files_to_sweep[nfiles].c_str(), errno);
		}
		else
		{
			opencount.release();
			free_ptr++;
		}
	}
	for (int n = 0; n < nthreads; n++)
	{
		fcount.acquire();
		fdescs[free_ptr++ % FDESCS] = -2;
	}
	opencount.release(nthreads);
}

// These two methods are used if a word is found.  The word is in the char[] buffer we read the file data into, and because that buffer will be
// reused later for a new read on other data, we can't safely just leave it there.  This is why we turn each word into a std::string at this point.
inline void found(int &tn, char *word)
{
	sub_count[tn][std::string(word)]++;
}

// This version is used if a word splits, with half in one chunk of a file, but the remainder in the next chunk.  For our std::string we need to
// recombine them into a single word, which in this case will live in a char[] on the stack while this version of found is active.
inline void found(int &tn, char *&prefix, char *&suffix)
{
	int plen = strlen(prefix);
	int slen = strlen(suffix);
	if (plen + slen >= 1023)
	{
		// In fact this never happens, but it is wiser to check!  Otherwise we could overrun the stack and corrupt the program memory
		printf("Word is unreasonably long! %s + %s (len %d)\n", prefix, suffix, plen + slen);
		return;
	}
	/// If we get here, we know that the new combined word will definitely fit into 1024 bytes, including the null (0) to terminate the word
	char word[1024];
	char *wp = word;
	memcpy(word, prefix, plen);
	memcpy(word + plen, suffix, slen + 1);
	found(tn, wp);
}

// This method is the "core" of the program.  It reads block by block through one file at a time, finding the words in the file and calling found
// The design is intended by as fast as feasible.
void wcounter(int n)
{
	char prefix_copy[1024];
	int fdesc;
	char *buffer = buffers[n];
	buffer[BLOCKSIZE] = 0;
	while (true)
	{
		{
			opencount.acquire();
			std::lock_guard<std::mutex> ltmp(lock);
			int slot = next_ptr++ % FDESCS;
			fdesc = fdescs[slot];
			fdescs[slot] = 0;
			file_count++;
		}
		if (fdesc == -2)
		{
			int bit = 1;
			--file_count;
			fcount.release();
			if (parallel_merge)
			{
				// 1 and 3 finish.
				// Now 0 will merge with counts from 1, 2 will merge with counts from 3, ...
				// Then 2 and 6 finish.
				// Now 0 will merge with 2, 4 will merge with 6, ...
				for (int partner = 1; n + partner < nthreads; partner <<= 1)
				{
					// Check to see if this thread should drop out
					if ((n & bit) != 0)
					{
						ready_for_merge[n]->release();
						return;
					}
					ready_for_merge[n + partner]->acquire();
					bit <<= 1;
					for (auto wc : sub_count[n + partner])
					{
						sub_count[n][wc.first] += wc.second;
					}
				}
			}
			ready_for_merge[n]->release();
			return;
		}
		int nbytes;
		char *prefix = nullptr;
		int sptr = -1;
		// Most of the "user time" of the program is spent in this loop
		while ((nbytes = read(fdesc, buffer, BLOCKSIZE)) > 0)
		{
			int cptr = 0;
			int bef = blocks_scanned;
			++blocks_scanned;
			int aft = blocks_scanned;
			buffer[nbytes] = 0;
			bytes_scanned += nbytes;
			while (cptr < nbytes)
			{
				// The pre-initialized array "token_chars" is the fastest way I could think of to check whether a character is in a-zA-Z0-9_
				// Obviously it can be done with a macro like "isalnum", but that macro involves if statements, and anyhow wouldn't include _
				// So I created a vector and each byte in it is true (included) or false (not included), using 1 for true and 0 for false.
				// This is read only, so even though multiple threads share it, they won't suffer a performance issue: it will quickly be in
				// every L2 cache and we'll get as good speed as if each had a local private copy!  I didn't use a vector of bits because
				// array index would have been more complicated if I had done so (more machine instructions... hence higher cost)
				if (token_chars[0xFF & (unsigned)buffer[cptr]] == 1)
				{
					if (sptr == -1)
					{
						// Found start of a new word
						sptr = cptr;
					}
				}
				else
				{
					// Because we will treat the buffer as if it contained a null-terminated C string, we need to null-terminate it!
					buffer[cptr] = 0;
					// We get here if we found a word but we need to check to see if it split over two file buffer reads, in which case
					// we would need to combine the two parts.
					found_something(n, buffer, prefix, sptr);
					sptr = -1;
				}
				cptr++;
			}
			// This next test and code block are to make a copy of a word at the end of a buffer, for that split case
			if (cptr == nbytes && sptr != -1)
			{
				int len = nbytes - sptr;
				prefix = prefix_copy;
				memcpy(prefix, buffer + sptr, len);
				prefix[len] = 0;
				sptr = -1;
			}
		}
		// This turned out to be unexpected: a surprising number of Linux .h and .c files "end" without a final newline character. They just end "in" a word, and
		// So we have to duplicate our logic to handle that.
		found_something(n, buffer, prefix, sptr);
		fcount.release();
		if (close(fdesc) == -1)
		{
			printf("Unable to close file: fdesc %d errno %d\n", fdesc, errno);
		}
	}
}

// Notice how the buffer, which is of type char[], has been changed into a pointer to the buffer for this call.  This is an oddity of the way that
// C handled arrays that was inherited into C++.  To me, it feels unnatural, but if C++ did the more obvious thing and just let me declare this as
// a character array "object" by reference, that would break back-compatibility with C.  A shame...
inline void found_something(int &n, char *&buffer, char *&prefix, int &sptr)
{
	// There are basically two cases: a word "entirely" in the buffer, or one "split" between the prior buffer and this one.
	// prefix is null if the word is entirely in the buffer, and we just can call found.  But if prefix is non-null, we
	// need to call our "split word" version of found to glue them together first.  One strange special case is if the prefix
	// actually was the full word after all: in that case we had a prefix copy waiting, but the first character of our buffer
	// wasn't a token-char, hence we can call the non-split case of found (this is cheaper than asking the split version to
	// make a copy, again, with a suffix that would actually be an empty string.
	if (prefix != nullptr)
	{
		if (sptr != -1)
		{
			char *sbptr = buffer + sptr;
			found(n, prefix, sbptr);
		}
		else
		{
			// Special case: it actually ended on the very last character of the prior buffer!
			found(n, prefix);
		}
		prefix = nullptr;
	}
	else if (sptr != -1)
	{
		found(n, buffer + sptr);
	}
	sptr = -1;
}

struct DefineSortOrder : public std::binary_function<std::pair<int, std::string>, std::pair<int, std::string>, bool>
{
	// In C++ this is one of the ways to define a non-standard sort order,  Given two objects that both have a (count, word) pair,
	// if the counts differ, put the bigger count first (so bigger counts print out first).  But for a tie, put the smaller word first,
	// using the standard alphabetic order.
	bool operator()(const std::pair<int, std::string> &lhs, const std::pair<int, std::string> &rhs) const
	{
		return lhs.first > rhs.first || (lhs.first == rhs.first && lhs.second < rhs.second);
	}
};

// Now we can define a new map sorted in this way.  The new type is called "SortOrder".
using SortOrder = std::map<std::pair<int, std::string>, std::pair<std::string, int>, DefineSortOrder>;

int main(int argc, char **argv)
{

	while (--argc && **(++argv) == '-')
	{
		switch (argv[0][1])
		{
		case 'n':
			nthreads = atoi(*argv + 2);
			break;
		case 'b':
			nblocks = std::min(atoi(*argv + 2), 127);
			break;
		case 'p':
			parallel_merge = true;
			break;
		case 's':
			silent = true;
			break;
		default:
			printf("Usage: fast-wc [-n#] dir...\n");
			return 1;
		}
	}
	if (argc == 0)
	{
		printf("No directory specified.\n");
		return 1;
	}
	BLOCKSIZE = nblocks * BASICBLOCK;
	if (!silent)
	{
		printf("fast-wc with %d cores, %d blocks per read, parallel merge %s\n", nthreads, nblocks, parallel_merge ? "ON" : "OFF");
	}
	auto str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_";
	while (*str)
	{
		token_chars[(int)*str++] = 1;
	}
	std::thread my_threads[MAXTHREADS];
	auto fot = std::thread(fopener, *argv);
	for (int n = 0; n < nthreads; n++)
	{
		ready_for_merge[n] = new std::counting_semaphore<1>(0);
		my_threads[n] = std::thread(wcounter, n);
	}
	// At this point, the file opener is running, opening files, and the n threads are scanning them.  Each one grabs the "next" open
	// file, reads blocks of bytes into a big char[] array, breaks out the words, then adds them to its own private "sub-count".
	// When the file opener is done it signals this (using a magic number: -2, which is never a legitimate file descriptor).  The
	// scanner threads running wcounter ("word counter") then shut down.
	for (int n = 0; n < nthreads; n++)
	{
		my_threads[n].join();
	}
	fot.join();

	
	if(file_count != expected_file_count) 
	{
		printf("Expected to scan %d files, but in fact scanned %d!\n", expected_file_count.load(), file_count.load());
		exit(0);
	}
	if(!silent)
	{
		printf("Blocks scanned: %d, bytes %d\n", blocks_scanned.load(), bytes_scanned.load());
		if(blocks_scanned.load() == 0 || bytes_scanned.load() == 0)
			exit(0);
	}

	SortOrder sorted_totals;
	if (!parallel_merge)
	{
		// So now all our threads are done, and we total the sub-counts.  In fact it would make some sense to just take one of the
		// subcounts as our running total, and this would let us scan one less of the sub-count trees.  But I didn't want to make things
		// more complicated (if I did that, the one we "pick" should ideally be on the same core as the main thread is on, but this
		// is a tiny bit fancier than we want to be in Lecture 1!), so we actually merge all n counts "into" a new total.
		WordCount totals;
		for (int n = 0; n < nthreads; n++)
		{
			for (auto [word, count] : sub_count[n])
			{
				totals[word] += count;
			}
		}
		// Total will be sorted by a default, namely the alphabetic sort on the keys (the words we found, including any numbers).  But we want
		// a fancy sort: first by total count, then sub-sorted by increasing alphabetic order.  So we defined a new map that sorts in this
		// fancy way.  THis sort adds about 3 seconds to total wall-clock elapsed time, on Ken's home computer (almost 20% of the total!)
		for (auto [word, count] : totals)
		{
			sorted_totals[{count, word}] = {word, count};
		}
	}
	else
	{
		// In this case, the merge was done in parallel and we just pull the merged data from thread 0 into the sort order
		for (auto [word, count] : sub_count[0])
		{
			sorted_totals[{count, word}] = {word, count};
		}
	}
	if (!silent)
	{
		for (auto w : sorted_totals)
		{
			// Print the string part of the key, using a field 32 characters long (or longer, for very long words), then an or-symbol, then the count
			printf("%32s   | %8d\n", w.second.first.c_str(), w.second.second);
		}
	}
	return 0;
}
