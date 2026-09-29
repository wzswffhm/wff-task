import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * COB-L4-002 贷款逐日计提与逾期监控批处理 Java 迁移版
 * （对应 COBOL 程序 CLN-LOANACCR 与子程序 CLN-DTUTIL）。
 */
class LoanAccrual {

    private static final BigDecimal ZERO = new BigDecimal("0.00");
    private static final BigDecimal ONE_POINT_FIVE = new BigDecimal("1.5");
    private static final BigDecimal BAND1 = new BigDecimal("50000.00");
    private static final BigDecimal BAND2 = new BigDecimal("200000.00");
    private static final BigDecimal MARGIN1 = new BigDecimal("1.00");
    private static final BigDecimal MARGIN2 = new BigDecimal("0.50");
    private static final BigDecimal MARGIN3 = new BigDecimal("0.00");
    private static final DateTimeFormatter BASIC = DateTimeFormatter.BASIC_ISO_DATE;
    private static final int SCALE = 2;

    private static final class Master {
        String acctNo;
        String name;
        String product;
        String curr;
        LocalDate openDate;
        BigDecimal principal;
        BigDecimal annualRate;
        String basis;
        int graceDays;
        LocalDate maturityDate;
        String status;
        LocalDate statusDate;
    }

    private static final class Tran {
        LocalDate valueDate;
        String code;
        BigDecimal amount;
    }

    private static final class RateAdj {
        LocalDate effDate;
        BigDecimal newRate;
    }

    private static final class FxRate {
        String curr;
        LocalDate effDate;
        BigDecimal rate;
    }

    private static final class Installment {
        LocalDate dueDate;
        LocalDate overdueStart;
        BigDecimal remaining;
    }

    private static final class Result {
        BigDecimal principal;
        BigDecimal normal;
        BigDecimal penalty;
        BigDecimal posted;
        BigDecimal repaid;
        BigDecimal overdue;
        BigDecimal fees;
        BigDecimal latefees;
        String status;
    }

    private static final class Totals {
        int accts = 0;
        BigDecimal principal = ZERO;
        BigDecimal normal = ZERO;
        BigDecimal penalty = ZERO;
        BigDecimal posted = ZERO;
        BigDecimal repaid = ZERO;
        BigDecimal overdue = ZERO;
        BigDecimal fees = ZERO;
        BigDecimal latefees = ZERO;
    }

    public static void main(String[] args) throws IOException {
        Path input = Paths.get("/app/input_files");
        Path output = Paths.get("/app/output");
        Files.createDirectories(output);

        LocalDate runDate = readRunDate(input.resolve("PROC_DATE.TXT"));
        List<Master> masters = readMasters(input);
        masters.sort(java.util.Comparator.comparing(m -> m.acctNo));
        Map<String, List<Tran>> transByAcct = readTrans(input);
        Map<String, List<RateAdj>> ratesByAcct = readRates(input);
        Map<String, List<Installment>> schedByAcct = readSchedules(input);
        Set<LocalDate> holidays = readHolidays(input);
        List<FxRate> fxRates = readFxRates(input.resolve("FX_RATE_USD.DAT"));
        validateParams(input, masters, transByAcct, runDate);

        Totals totals = new Totals();
        Map<String, Totals> byCurr = new java.util.LinkedHashMap<>();
        List<String> lines = new ArrayList<>();
        for (Master m : masters) {
            Result r = compute(m,
                    transByAcct.getOrDefault(m.acctNo, new ArrayList<>()),
                    ratesByAcct.getOrDefault(m.acctNo, new ArrayList<>()),
                    schedByAcct.getOrDefault(m.acctNo, new ArrayList<>()),
                    holidays, runDate, fxRates);
            lines.add(formatDetail(m, r));
            accumulate(totals, r);
            String ccy = m.curr == null ? "CNY" : m.curr;
            Totals tc = byCurr.computeIfAbsent(ccy, k -> new Totals());
            accumulate(tc, r);
        }
        lines.add(formatTotal(totals));

        Files.write(output.resolve("COB-L4-002_AccrualResult.txt"),
                lines, StandardCharsets.UTF_8);

        List<String> slines = new ArrayList<>();
        for (java.util.Map.Entry<String, Totals> e : byCurr.entrySet()) {
            slines.add(formatCurrency(e.getKey(), e.getValue()));
        }
        slines.add(formatTotal(totals));
        Files.write(output.resolve("COB-L4-002_SummaryByCurrency.txt"),
                slines, StandardCharsets.UTF_8);
    }

    private static LocalDate readRunDate(Path p) throws IOException {
        for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
            String s = line.trim();
            if (!s.isEmpty()) {
                return LocalDate.parse(s, BASIC);
            }
        }
        throw new IOException("PROC_DATE.TXT is empty");
    }

    private static List<Master> readMasters(Path dir) throws IOException {
        List<Master> out = new ArrayList<>();
        for (Path p : listFiles(dir, "ACCT_MASTER_", ".DAT")) {
            for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
                if (line.isEmpty()) continue;
                Master m = new Master();
                m.acctNo = line.substring(0, 10);
                m.name = line.substring(10, 34);
                m.product = line.substring(34, 38);
                m.curr = line.substring(38, 42).trim();
                m.openDate = LocalDate.parse(line.substring(42, 50), BASIC);
                m.principal = new BigDecimal(line.substring(50, 64)).movePointLeft(2);
                m.annualRate = new BigDecimal(line.substring(64, 70)).movePointLeft(4);
                m.basis = line.substring(70, 74);
                m.graceDays = Integer.parseInt(line.substring(74, 77));
                m.maturityDate = LocalDate.parse(line.substring(77, 85), BASIC);
                m.status = line.substring(85, 86);
                String sd = line.substring(86, 94);
                m.statusDate = sd.equals("00000000") ? null : LocalDate.parse(sd, BASIC);
                out.add(m);
            }
        }
        return out;
    }

    private static Map<String, List<Tran>> readTrans(Path dir) throws IOException {
        Map<String, List<Tran>> map = new HashMap<>();
        for (Path p : listFiles(dir, "TRAN_HIST_", ".DAT")) {
            for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
                if (line.isEmpty()) continue;
                Tran t = new Tran();
                String acct = line.substring(0, 10).trim();
                t.valueDate = LocalDate.parse(line.substring(18, 26), BASIC);
                t.code = line.substring(26, 30).trim();
                t.amount = new BigDecimal(line.substring(30, 45)).movePointLeft(2);
                map.computeIfAbsent(acct, k -> new ArrayList<>()).add(t);
            }
        }
        return map;
    }

    private static Map<String, List<RateAdj>> readRates(Path dir) throws IOException {
        Map<String, List<RateAdj>> map = new HashMap<>();
        for (Path p : listFiles(dir, "RATE_ADJ_", ".DAT")) {
            for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
                if (line.isEmpty()) continue;
                RateAdj a = new RateAdj();
                String acct = line.substring(0, 10).trim();
                a.effDate = LocalDate.parse(line.substring(10, 18), BASIC);
                a.newRate = new BigDecimal(line.substring(18, 24)).movePointLeft(4);
                map.computeIfAbsent(acct, k -> new ArrayList<>()).add(a);
            }
        }
        return map;
    }

    private static Map<String, List<Installment>> readSchedules(Path dir) throws IOException {
        Map<String, List<Installment>> map = new HashMap<>();
        for (Path p : listFiles(dir, "SCHED_", ".DAT")) {
            for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
                if (line.isEmpty()) continue;
                Installment ins = new Installment();
                String acct = line.substring(0, 10).trim();
                ins.dueDate = LocalDate.parse(line.substring(10, 18), BASIC);
                ins.remaining = new BigDecimal(line.substring(18, 32)).movePointLeft(2);
                map.computeIfAbsent(acct, k -> new ArrayList<>()).add(ins);
            }
        }
        return map;
    }

    private static List<Path> listFiles(Path dir, String prefix, String suffix) throws IOException {
        try (java.util.stream.Stream<Path> s = Files.list(dir)) {
            return s.filter(p -> p.getFileName().toString().startsWith(prefix)
                    && p.getFileName().toString().endsWith(suffix))
                    .sorted().collect(java.util.stream.Collectors.toList());
        }
    }

    private static List<FxRate> readFxRates(Path p) throws IOException {
        List<FxRate> out = new ArrayList<>();
        for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
            if (line.isEmpty()) continue;
            FxRate f = new FxRate();
            f.curr = line.substring(0, 4).trim();
            f.effDate = LocalDate.parse(line.substring(4, 12), BASIC);
            f.rate = new BigDecimal(line.substring(12, 20)).movePointLeft(4);
            out.add(f);
        }
        return out;
    }

    private static BigDecimal fxRate(LocalDate day, List<FxRate> fx) {
        BigDecimal r = BigDecimal.ONE;
        for (FxRate f : fx) {
            if (f.curr.equals("USD") && !f.effDate.isAfter(day)) {
                r = f.rate;
            }
        }
        return r;
    }

    private static Set<LocalDate> readHolidays(Path dir) throws IOException {
        Set<LocalDate> out = new HashSet<>();
        for (Path p : listFiles(dir, "CAL_", ".DAT")) {
            for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
                String s = line.trim();
                if (!s.isEmpty()) {
                    out.add(LocalDate.parse(s, BASIC));
                }
            }
        }
        return out;
    }

    private static boolean isBusinessDay(LocalDate d, Set<LocalDate> holidays) {
        if (d.getDayOfWeek() == DayOfWeek.SATURDAY || d.getDayOfWeek() == DayOfWeek.SUNDAY) {
            return false;
        }
        return !holidays.contains(d);
    }

    private static LocalDate advanceBusinessDays(LocalDate from, int steps, Set<LocalDate> holidays) {
        LocalDate cur = from;
        for (int i = 0; i < steps; i++) {
            cur = cur.plusDays(1);
            while (!isBusinessDay(cur, holidays)) {
                cur = cur.plusDays(1);
            }
        }
        return cur;
    }

    private static BigDecimal marginOf(BigDecimal principal) {
        if (principal.compareTo(BAND1) <= 0) return MARGIN1;
        if (principal.compareTo(BAND2) <= 0) return MARGIN2;
        return MARGIN3;
    }

    private static boolean lastDayOfMonth(LocalDate day) {
        return day.getDayOfMonth() == day.lengthOfMonth();
    }

    private static Result compute(Master m, List<Tran> trans, List<RateAdj> rates,
                                  List<Installment> installments, Set<LocalDate> holidays,
                                  LocalDate runDate, List<FxRate> fxRates) {
        boolean isUsd = m.curr != null && m.curr.equals("USD");
        BigDecimal fxOpen = isUsd ? fxRate(m.openDate, fxRates) : BigDecimal.ONE;
        BigDecimal principal = m.principal.multiply(fxOpen).setScale(2, RoundingMode.HALF_UP);
        BigDecimal accruedN = ZERO;
        BigDecimal accruedP = ZERO;
        BigDecimal posted = ZERO;
        BigDecimal repaid = ZERO;
        BigDecimal fees = ZERO;
        BigDecimal latefees = ZERO;
        boolean closed = false;

        trans.sort(Comparator.comparing(t -> t.valueDate));
        rates.sort(Comparator.comparing(a -> a.effDate));
        installments.sort(Comparator.comparing(i -> i.dueDate));
        for (Installment ins : installments) {
            ins.overdueStart = advanceBusinessDays(ins.dueDate, m.graceDays + 1, holidays);
            ins.remaining = ins.remaining.multiply(fxOpen).setScale(2, RoundingMode.HALF_UP);
        }

        int idx = 0;
        for (LocalDate day = m.openDate; !day.isAfter(runDate); day = day.plusDays(1)) {
            while (idx < trans.size() && trans.get(idx).valueDate.equals(day)) {
                Tran t = trans.get(idx);
                switch (t.code) {
                    case "DISB":
                        principal = principal.add(t.amount.multiply(fxOpen).setScale(2, RoundingMode.HALF_UP));
                        break;
                    case "RPAY": {
                        BigDecimal pay = t.amount.negate().multiply(fxOpen).setScale(2, RoundingMode.HALF_UP);
                        BigDecimal takeP = pay.min(accruedP);
                        accruedP = accruedP.subtract(takeP);
                        pay = pay.subtract(takeP);
                        BigDecimal takeF = pay.min(fees);
                        fees = fees.subtract(takeF);
                        pay = pay.subtract(takeF);
                        BigDecimal takeLF = pay.min(latefees);
                        latefees = latefees.subtract(takeLF);
                        pay = pay.subtract(takeLF);
                        BigDecimal takeN = pay.min(accruedN);
                        accruedN = accruedN.subtract(takeN);
                        pay = pay.subtract(takeN);
                        principal = principal.subtract(pay);
                        repaid = repaid.add(pay);
                        for (Installment ins : installments) {
                            if (pay.signum() <= 0) break;
                            if (ins.remaining.signum() > 0) {
                                BigDecimal take = pay.min(ins.remaining);
                                ins.remaining = ins.remaining.subtract(take);
                                pay = pay.subtract(take);
                            }
                        }
                        break;
                    }
                    case "PINT":
                        posted = posted.add(t.amount);
                        principal = principal.add(t.amount);
                        accruedN = ZERO;
                        accruedP = ZERO;
                        break;
                    case "FEE":
                        fees = fees.add(t.amount.multiply(fxOpen).setScale(2, RoundingMode.HALF_UP));
                        break;
                    case "LFE":
                        latefees = latefees.add(t.amount.multiply(fxOpen).setScale(2, RoundingMode.HALF_UP));
                        break;
                    case "CLSE":
                        repaid = repaid.add(principal);
                        principal = ZERO;
                        accruedN = ZERO;
                        accruedP = ZERO;
                        for (Installment ins : installments) {
                            ins.remaining = ZERO;
                        }
                        closed = true;
                        break;
                    default:
                        break;
                }
                idx++;
            }

            BigDecimal overdue = ZERO;
            for (Installment ins : installments) {
                if (ins.remaining.signum() > 0 && !day.isBefore(ins.overdueStart)) {
                    overdue = overdue.add(ins.remaining);
                }
            }

            boolean suspend = closed || (m.status.equals("N") || m.status.equals("L"))
                    && m.statusDate != null && !day.isBefore(m.statusDate);
            if (!suspend) {
                BigDecimal base = principal.subtract(overdue);
                if (base.signum() < 0) base = ZERO;
                BigDecimal rate = m.annualRate;
                for (RateAdj a : rates) {
                    if (!a.effDate.isAfter(day)) {
                        rate = a.newRate;
                    }
                }
                BigDecimal eff = rate.signum() == 0 ? ZERO : rate.add(marginOf(principal));
                if (base.signum() > 0) {
                    if (m.basis.equals("B30D")) {
                        if (lastDayOfMonth(day)) {
                            accruedN = accruedN.add(base.multiply(eff)
                                    .divide(BigDecimal.valueOf(1200L), SCALE, RoundingMode.HALF_UP));
                        }
                    } else {
                        int div = m.basis.equals("A365") ? 365 : 360;
                        accruedN = accruedN.add(base.multiply(eff)
                                .divide(BigDecimal.valueOf(div * 100L), SCALE, RoundingMode.HALF_UP));
                    }
                }
                if (overdue.signum() > 0) {
                    BigDecimal penRate = eff.multiply(ONE_POINT_FIVE);
                    accruedP = accruedP.add(overdue.multiply(penRate)
                            .divide(BigDecimal.valueOf(36500L), SCALE, RoundingMode.HALF_UP));
                }
            }
        }

        Result r = new Result();
        r.principal = principal;
        r.normal = accruedN;
        r.penalty = accruedP;
        r.posted = posted;
        r.repaid = repaid;
        r.overdue = overdueTotal(installments, runDate);
        r.fees = fees;
        r.latefees = latefees;
        r.status = closed ? "C" : m.status;
        return r;
    }

    private static BigDecimal overdueTotal(List<Installment> installments, LocalDate runDate) {
        BigDecimal od = ZERO;
        for (Installment ins : installments) {
            if (ins.remaining.signum() > 0 && !runDate.isBefore(ins.overdueStart)) {
                od = od.add(ins.remaining);
            }
        }
        return od;
    }

    private static void accumulate(Totals t, Result r) {
        t.accts += 1;
        t.principal = t.principal.add(r.principal);
        t.normal = t.normal.add(r.normal);
        t.penalty = t.penalty.add(r.penalty);
        t.posted = t.posted.add(r.posted);
        t.repaid = t.repaid.add(r.repaid);
        t.overdue = t.overdue.add(r.overdue);
        t.fees = t.fees.add(r.fees);
        t.latefees = t.latefees.add(r.latefees);
    }

    private static String formatDetail(Master m, Result r) {
        StringBuilder sb = new StringBuilder();
        sb.append(pad(m.acctNo, 10)).append('|')
          .append(pad(m.name, 24)).append('|')
          .append(pad(m.product, 4)).append('|')
          .append(fmt(r.principal)).append('|')
          .append(fmt(r.normal)).append('|')
          .append(fmt(r.penalty)).append('|')
          .append(fmt(r.normal.add(r.penalty))).append('|')
          .append(fmt(r.posted)).append('|')
          .append(fmt(r.repaid)).append('|')
          .append(fmt(r.overdue)).append('|')
          .append(fmt(r.fees)).append('|')
          .append(fmt(r.latefees)).append('|')
          .append(pad(m.basis, 4)).append('|')
          .append(r.status);
        return sb.toString();
    }

    private static String formatCurrency(String ccy, Totals t) {
        return String.format(Locale.ROOT,
                "CURRENCY=%s|ACCTS=%d|PRINCIPAL=%015.2f|NORMAL=%015.2f|PENALTY=%015.2f|ACCRUED=%015.2f|POSTED=%015.2f|REPAID=%015.2f|OVERDUE=%015.2f|FEES=%015.2f|LATEFEES=%015.2f",
                ccy, t.accts, t.principal, t.normal, t.penalty, t.normal.add(t.penalty),
                t.posted, t.repaid, t.overdue, t.fees, t.latefees);
    }

    private static String formatTotal(Totals t) {
        return String.format(Locale.ROOT,
                "TOTAL|ACCTS=%d|PRINCIPAL=%015.2f|NORMAL=%015.2f|PENALTY=%015.2f|ACCRUED=%015.2f|POSTED=%015.2f|REPAID=%015.2f|OVERDUE=%015.2f|FEES=%015.2f|LATEFEES=%015.2f",
                t.accts, t.principal, t.normal, t.penalty, t.normal.add(t.penalty),
                t.posted, t.repaid, t.overdue, t.fees, t.latefees);
    }

    private static String fmt(BigDecimal v) {
        return String.format(Locale.ROOT, "%015.2f", v);
    }

    private static String pad(String s, int width) {
        if (s.length() >= width) {
            return s.substring(0, width);
        }
        StringBuilder sb = new StringBuilder(s);
        while (sb.length() < width) {
            sb.append(' ');
        }
        return sb.toString();
    }

    private static void validateParams(Path dir, List<Master> masters,
            Map<String, List<Tran>> transByAcct, LocalDate runDate) throws IOException {
        Set<String> prods = readCodeSet(dir.resolve("PROD_PARAM.DAT"), 4);
        Set<String> ccys = readCodeSet(dir.resolve("CCY_PARAM.DAT"), 4);
        Set<String> basis = readCodeSet(dir.resolve("BASIS_CODE.DAT"), 4);
        Set<String> status = readCodeSet(dir.resolve("STATUS_CODE.DAT"), 1);
        Set<String> trns = readCodeSet(dir.resolve("TRN_CODE.DAT"), 4);
        for (Master m : masters) {
            if (!prods.contains(m.product)) throw new IOException("unknown product: " + m.product);
            if (!ccys.contains(m.curr)) throw new IOException("unknown currency: " + m.curr);
            if (!basis.contains(m.basis)) throw new IOException("unknown basis: " + m.basis);
            if (!status.contains(m.status)) throw new IOException("unknown status: " + m.status);
        }
        for (java.util.Map.Entry<String, List<Tran>> e : transByAcct.entrySet()) {
            for (Tran t : e.getValue()) {
                if (!trns.contains(t.code)) throw new IOException("unknown trn code: " + t.code);
            }
        }
        boolean batchOk = false;
        for (String line : Files.readAllLines(dir.resolve("BATCH_PARAM.DAT"), StandardCharsets.UTF_8)) {
            String s = line.trim();
            if (!s.isEmpty()) {
                LocalDate bd = LocalDate.parse(s.substring(9, 17), BASIC);
                if (bd.equals(runDate)) batchOk = true;
            }
        }
        if (!batchOk) throw new IOException("BATCH_PARAM run date mismatch");
        // FEE_PARAM：费用代码唯一，金额为定长 12 位非负十进制数
        Set<String> feeCodes = new HashSet<>();
        for (String line : Files.readAllLines(dir.resolve("FEE_PARAM.DAT"), StandardCharsets.UTF_8)) {
            String s = line.trim();
            if (s.isEmpty()) continue;
            if (s.length() < 15) throw new IOException("FEE_PARAM malformed: " + s);
            String amtStr = s.substring(s.length() - 12).trim();
            if (!amtStr.matches("\\d{1,12}")) throw new IOException("FEE_PARAM bad amount: " + amtStr);
            String code = s.substring(0, s.length() - 12).trim();
            if (code.isEmpty() || !feeCodes.add(code)) throw new IOException("FEE_PARAM bad/dup code: " + code);
        }
        // TAX_PARAM：税率代码唯一，税率为定长 5 位十进制数
        for (String line : Files.readAllLines(dir.resolve("TAX_PARAM.DAT"), StandardCharsets.UTF_8)) {
            String s = line.trim();
            if (s.isEmpty()) continue;
            if (s.length() < 8) throw new IOException("TAX_PARAM malformed: " + s);
            String rateStr = s.substring(s.length() - 5).trim();
            if (!rateStr.matches("\\d{1,5}")) throw new IOException("TAX_PARAM bad rate: " + rateStr);
        }
        // ORG_PARAM：机构代码为 6 位数字且唯一
        Set<String> orgs = new HashSet<>();
        for (String line : Files.readAllLines(dir.resolve("ORG_PARAM.DAT"), StandardCharsets.UTF_8)) {
            String s = line.trim();
            if (s.isEmpty()) continue;
            if (s.length() < 9) throw new IOException("ORG_PARAM malformed: " + s);
            String code = s.substring(0, 6).trim();
            if (!code.matches("\\d{6}") || !orgs.add(code)) throw new IOException("ORG_PARAM bad/dup org: " + code);
        }
        // GL_MAP：每个产品须有 INT/PRN/PEN 科目映射，产品集合与 PROD_PARAM 一致
        Set<String> glProds = new HashSet<>();
        for (String line : Files.readAllLines(dir.resolve("GL_MAP.DAT"), StandardCharsets.UTF_8)) {
            String s = line.trim();
            if (s.isEmpty()) continue;
            if (s.length() != 37) throw new IOException("GL_MAP malformed: " + s);
            glProds.add(s.substring(0, 4).trim());
        }
        if (!glProds.equals(prods)) throw new IOException("GL_MAP product set mismatch");
    }

    private static Set<String> readCodeSet(Path p, int len) throws IOException {
        Set<String> out = new HashSet<>();
        for (String line : Files.readAllLines(p, StandardCharsets.UTF_8)) {
            String s = line.trim();
            if (!s.isEmpty()) {
                out.add(s.substring(0, len).trim());
            }
        }
        return out;
    }
}
